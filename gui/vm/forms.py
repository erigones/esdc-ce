from django import forms
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.template.defaultfilters import filesizeformat
# noinspection PyProtectedMember
from django.forms.forms import NON_FIELD_ERRORS
from datetime import datetime
import pytz
import re

from api.mon import MonitoringBackend
from pdns.models import Record
from vms.models import Vm, Snapshot, Backup, BackupDefine
from vms.utils import AttrDict
from gui.forms import SerializerForm
from gui.utils import tags_to_string
from gui.fields import ArrayField, DictField, TagField
from gui.widgets import NumberInput, ArrayWidget, DictWidget, TagWidget
from gui.vm.widgets import DataSelect, MetaDataSelect
from gui.vm.utils import get_vm_define, get_vm_define_disk, get_vm_define_nic
# noinspection PyProtectedMember
from gui.dc.image.forms import _ImageForm
from api.vm.utils import get_templates, get_nodes, get_images, get_subnets, get_zpools, get_owners
from api.vm.define.vm_define_disk import DISK_ID_MIN, DISK_ID_MAX, DISK_ID_MAX_BHYVE, DISK_ID_MAX_OS
from api.vm.define.vm_define_nic import NIC_ID_MIN, NIC_ID_MAX
from api.vm.define.views import vm_define, vm_define_user, vm_define_disk, vm_define_nic, vm_define_revert
from api.vm.snapshot.views import vm_define_snapshot, image_snapshot
from api.vm.backup.views import vm_define_backup

DISK_ID_MIN += 1
DISK_ID_MAX += 1
DISK_ID_MAX_BHYVE += 1
DISK_ID_MAX_OS += 1
NIC_ID_MIN += 1
NIC_ID_MAX += 1

REQUIRED = {'required': 'required'}


def disk_id_option(array_disk_id, disk):
    """Text for option in Disk ID select field"""
    return _('Disk') + ' %d (%s)' % (array_disk_id, filesizeformat(int(disk['size']) * 1048576))


def vm_disk_id_choices(vm):
    """Return list of available disk IDs for v VM"""
    return [(i + 1, disk_id_option(i + 1, disk)) for i, disk in enumerate(vm.json_active_get_disks())]


class PTRForm(forms.Form):
    """
    Form for changing reverse DNS name of IP on VM's nics.
    """
    content = forms.RegexField(label=_('Reverse DNS name'), regex=r'^[a-z0-9][a-z0-9.-]+[a-z0-9]$',
                               max_length=1024, min_length=4,
                               widget=forms.TextInput(attrs={'class': 'input-transparent', 'required': 'required',
                                                             'style': 'width: 200px;', 'pattern': '[a-z0-9.-]+'}))

    def set_api_errors(self, data):
        """All errors except content related are transformed to non_field_errors"""
        errors = data.get('result', data)

        if isinstance(errors, dict) and errors:
            if NON_FIELD_ERRORS not in self._errors:
                self._errors[NON_FIELD_ERRORS] = self.error_class()

            for key, val in errors.items():
                if key in self.fields:
                    self._errors[key] = self.error_class(val)
                else:
                    if not isinstance(val, list):
                        val = (val,)

                    for err in val:
                        self._errors[NON_FIELD_ERRORS].append('%s: %s' % (key, err))


class HostnameForm(forms.Form):
    """
    Inherit from this to get the disabled hostname field.
    """
    hostname = forms.CharField(label=_('Hostname'), required=True,
                               widget=forms.TextInput(attrs={'class': 'input-transparent narrow uneditable-input',
                                                             'disabled': 'disabled'}))


class ServerSettingsForm(SerializerForm):
    """
    Form for changing VM's settings (alias and hostname).
    """
    admin = False
    _api_call = vm_define_user

    alias = forms.RegexField(label=_('Short server name'), required=True,
                             regex=r'^[A-Za-z0-9][A-Za-z0-9.-]+[A-Za-z0-9]$', max_length=24, min_length=4,
                             widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                           'required': 'required',
                                                           'pattern': '[A-Za-z0-9.-]+'}))
    # The hostname part of FQDN
    hostname = forms.RegexField(label=_('Server hostname'), required=True, regex=r'^[a-z0-9][a-z0-9.-]+[a-z0-9]$',
                                max_length=64, min_length=3,
                                widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                              'required': 'required',
                                                              'pattern': '[a-z0-9.-]+'}))
    # The domain part of FQDN
    domain = forms.TypedChoiceField(label=_('DNS domain name'), required=True, coerce=str, empty_value=None,
                                    widget=forms.Select(attrs={'class': 'control-inline narrow input-select2'}))

    def _initial_data(self, request, vm):
        return {
            'alias': vm.alias,
            'hostname': vm.fqdn_hostname,
            'domain': vm.fqdn_domain,
        }

    def __init__(self, request, vm, *args, **kwargs):
        self.dns = None
        self.dns_content = None

        # Cache vm._fqdn hostname/domain pair and find dns record
        # This will also fill the _available_domains list
        if vm and vm.hostname_is_valid_fqdn(cache=False):  # Will return False if DNS_ENABLED is False
            self.dns = Record.get_records_A(vm.hostname, vm.fqdn_domain)
            if self.dns:
                self.dns_content = ', '.join([d.content for d in self.dns])

        # Initial data
        if vm and 'initial' not in kwargs:
            kwargs['initial'] = self._initial_data(request, vm)

        # Parent constructor
        super(ServerSettingsForm, self).__init__(request, vm, *args, **kwargs)

        if vm:
            # noinspection PyProtectedMember
            domains = [(i, i) for i in vm._available_domains]
            # Invalid (empty) domain must be added into domain choices
            if not vm.fqdn_domain:
                domains.append(('', ''))
                self.fields['domain'].required = False
        else:
            domains = [(i, i) for i in Vm.available_domains(request.dc, request.user)]
            if not request.dc.settings.DNS_ENABLED:
                self.fields['domain'].required = False

        # Set available domains
        domains.sort()
        self.fields['domain'].choices = domains

    @property
    def _vm_hostname(self):
        hostname = self.cleaned_data.get('hostname')
        domain = self.cleaned_data.get('domain')

        if domain:
            return hostname + '.' + domain
        return hostname

    @property
    def current_hostname(self):
        if self._obj:
            return self._obj.hostname
        return self._vm_hostname

    @property
    def saved_hostname(self):
        assert self._api_response, 'API view must be called first'
        return self._api_response['result']['hostname']

    def _final_data(self, data=None):
        # noinspection PyProtectedMember
        ret = super(ServerSettingsForm, self)._final_data(data=data)
        new_hostname = self._vm_hostname

        if not self._obj or new_hostname != self.current_hostname:
            ret['hostname'] = new_hostname

        try:
            del ret['domain']
        except KeyError:
            pass

        return ret


class AdminServerSettingsForm(ServerSettingsForm):
    """
    Copy of vm_define serializer (api).
    """
    admin = True
    _api_call = vm_define

    tags = TagField(label=_('Tags'), required=False,
                    widget=TagWidget(attrs={'class': 'tags-select2 narrow'}),
                    help_text=_('The tag will be created in case it does not exist.'))
    node = forms.TypedChoiceField(label=_('Node'), required=False, coerce=str, empty_value=None,
                                  widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    template = forms.TypedChoiceField(label=_('Template'), required=False, coerce=str, empty_value=None,
                                      help_text=_('Setting template can modify lots of server attributes, '
                                                  'e.g. disks, nics.'),
                                      widget=DataSelect(attrs={'class': 'narrow input-select2'}))
    ostype = forms.TypedChoiceField(label=_('OS Type'), choices=Vm.OSTYPE, required=True, coerce=int,
                                    widget=forms.Select(attrs={'class': 'input-select2 narrow ostype-select',
                                                               'required': 'required',
                                                               'onChange': 'update_vm_form_fields_from_ostype()'}))
    hvm_type = forms.TypedChoiceField(label=_('Hypervisor Type'), choices=Vm.HVM_TYPE_GUI, required=False, coerce=int,
                                      widget=forms.Select(attrs={'class': 'input-select2 narrow hvm-type-select',
                                                                 'required': 'required',
                                                                 'onChange': 'update_vm_form_fields_from_hvm_type()'}))
    vcpus = forms.IntegerField(label=_('VCPUs'), required=False,
                               widget=NumberInput(attrs={'class': 'input-transparent narrow', 'required': 'required'}))
    # noinspection SpellCheckingInspection
    ram = forms.IntegerField(label=_('RAM'), required=False,
                             widget=forms.TextInput(attrs={'class': 'input-transparent narrow input-mbytes',
                                                           'required': 'required',
                                                           'pattern': '[0-9.]+[BKMGTPEbkmgtpe]?'}))
    note = forms.CharField(label=_('Note'), help_text=_('Text with markdown support, visible to every user with access '
                                                        'to this server.'),
                           required=False,
                           widget=forms.Textarea(attrs={
                               'class': 'input-transparent',
                               'rows': 5})
                           )
    monitored = forms.BooleanField(label=_('Monitored?'), required=False,
                                   widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    installed = forms.BooleanField(label=_('Installed?'), required=False,
                                   help_text=_('This field is used for informational purposes only.'),
                                   widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    snapshot_limit_manual = forms.IntegerField(label=_('Snapshot count limit'), required=False,
                                               widget=NumberInput(attrs={'class': 'input-transparent narrow'}),
                                               help_text=_('Maximum number of manual server snapshots.'))
    snapshot_size_percent_limit = forms.IntegerField(label=_('Snapshot size % limit'), required=False,
                                                     widget=NumberInput(attrs={'class': 'input-transparent narrow'}),
                                                     help_text=_(
                                                         'Maximum size of all server snapshots as % of all disk space '
                                                         'of this VM (example: 200% = VM with 10GB disk(s) can have '
                                                         '20GB of snapshots).'))
    snapshot_size_limit = forms.IntegerField(label=_('Snapshot size limit'), required=False,
                                             widget=NumberInput(attrs={'class': 'input-transparent narrow'}),
                                             help_text=_('Maximum size of all server snapshots. '
                                                         'If set, it takes precedence over % limit.'))
    cpu_shares = forms.IntegerField(label=_('CPU Shares'), max_value=1048576, min_value=0, required=True,
                                    widget=NumberInput(attrs={'class': 'input-transparent narrow',
                                                              'required': 'required'}))
    # cpu_cap = forms.IntegerField(label=_('CPU Capping'), max_value=6400, min_value=0, required=False,
    #                             widget=NumberInput(attrs={'class': 'input-transparent narrow'}))
    zfs_io_priority = forms.IntegerField(label=_('IO Priority'), max_value=1024, min_value=0, required=True,
                                         widget=NumberInput(attrs={'class': 'input-transparent narrow',
                                                                   'required': 'required'}))
    bootrom = forms.ChoiceField(label=_('Bootrom'), required=False,
                                widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    zpool = forms.ChoiceField(label=_('Storage'), required=False,
                              widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    owner = forms.ChoiceField(label=_('Owner'), required=False,
                              widget=forms.Select(attrs={'class': 'narrow input-select2'}))

    monitoring_templates = ArrayField(label=_('Monitoring templates'), required=False, tags=True,
                                      help_text=_('Comma-separated list of custom monitoring templates.'),
                                      widget=ArrayWidget(tags=True, escape_space=False,
                                                         attrs={'class': 'tags-select2 narrow'}))
    monitoring_hostgroups = ArrayField(label=_('Monitoring hostgroups'), required=False, tags=True,
                                       validators=[
                                           RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS)],
                                       help_text=_('Comma-separated list of custom monitoring hostgroups.'),
                                       widget=ArrayWidget(tags=True, escape_space=False,
                                                          attrs={'class': 'tags-select2 narrow'}))
    mdata = DictField(label=_('Metadata'), required=False,
                      help_text=_('key=value string pairs.'),
                      widget=DictWidget(attrs={
                          'class': 'input-transparent small',
                          'rows': 5,
                          'data-raw_input_enabled': 'true',
                      }))

    def __init__(self, request, vm, *args, **kwargs):
        super(AdminServerSettingsForm, self).__init__(request, vm, *args, **kwargs)
        dc_settings = request.dc.settings
        # Set choices
        self.vm_nodes = get_nodes(request, is_compute=True)
        # TODO: node.color
        self.fields['node'].choices = [('', _('(auto)'))] + [(i.hostname, i.hostname) for i in self.vm_nodes]
        self.fields['owner'].choices = get_owners(request).values_list('username', 'username')
        self.fields['zpool'].choices = get_zpools(request).values_list('zpool', 'storage__alias').distinct()
        self.fields['bootrom'].choices = Vm.BHYVE_BOOTROM

        if not request.user.is_staff:
            self.fields['cpu_shares'].widget.attrs['disabled'] = 'disabled'
            self.fields['cpu_shares'].widget.attrs['class'] += ' uneditable-input'
            self.fields['zfs_io_priority'].widget.attrs['disabled'] = 'disabled'
            self.fields['zfs_io_priority'].widget.attrs['class'] += ' uneditable-input'

        if dc_settings.MON_ZABBIX_TEMPLATES_VM_RESTRICT:
            self.fields['monitoring_templates'].widget.tag_choices = dc_settings.MON_ZABBIX_TEMPLATES_VM_ALLOWED

        if dc_settings.MON_ZABBIX_HOSTGROUPS_VM_RESTRICT:
            self.fields['monitoring_hostgroups'].widget.tag_choices = dc_settings.MON_ZABBIX_HOSTGROUPS_VM_ALLOWED

        if dc_settings.MON_ZABBIX_HOSTGROUPS_VM:
            self.fields['monitoring_hostgroups'].help_text += _(' Automatically added hostgroups: ') \
                                                              + ', '.join(dc_settings.MON_ZABBIX_HOSTGROUPS_VM)

        if vm:
            empty_template_data = {}
            self.fields['ostype'].widget.attrs['disabled'] = 'disabled'
            self.fields['hvm_type'].widget.attrs['disabled'] = 'disabled'
            if not vm.is_hvm():
                # for zones the only HVM choice is NO hypervisor
                self.fields['hvm_type'].choices = Vm.HVM_TYPE_GUI_NO_HYPERVISOR

            if vm.is_deployed():
                self.fields['node'].widget.attrs['class'] += ' disable_created2'
                self.fields['zpool'].widget.attrs['class'] += ' disable_created2'
        else:
            empty_template_data = self.initial
            ostype = Vm.OSTYPE

            # Disable zone support _only_ when adding new VM (zone must be available in edit mode) - Issue #chili-461
            if not dc_settings.VMS_ZONE_ENABLED:
                # Remove SunOS Zone support
                ostype = [i for i in ostype if i[0] not in Vm.ZONE_OSTYPES]

            self.fields['ostype'].choices = ostype

        empty_template = AttrDict({'alias': _('(none)'), 'desc': '', 'web_data': empty_template_data})
        self.fields['template'].choices = [('', empty_template)] + [(i.name, i) for i in get_templates(request)]

    def _initial_data(self, request, vm):
        fix = super(AdminServerSettingsForm, self)._initial_data(request, vm)
        ret = get_vm_define(request, vm)
        # We need string representation of tags, but vm_define returns a list
        if 'tags' in ret:
            ret['tags'] = tags_to_string(ret['tags'])
        # Some serializer data need to be replaced by data expected by the parent form
        ret.update(fix)

        return ret


class ServerDiskSettingsForm(SerializerForm):
    """
    Partial copy of vm_define_disk serializer (api).
    """

    admin = False
    _api_call = vm_define_disk

    def __init__(self, request, vm, *args, **kwargs):
        super(ServerDiskSettingsForm, self).__init__(request, vm, *args, **kwargs)

        max_disks = DISK_ID_MAX
        if vm.is_hvm():
            if vm.is_kvm():
                model_choices = Vm.DISK_MODEL_KVM
            else:  # bhyve
                model_choices = Vm.DISK_MODEL_BHYVE
                max_disks = DISK_ID_MAX_BHYVE

            self.fields['model'] = forms.ChoiceField(label=_('Model'), choices=model_choices, required=False,
                                                     widget=forms.Select(attrs={'class': 'narrow input-select2'}))

        # zone
        elif 'model' in self.fields:
            del self.fields['model']

        self.fields['disk_id'] = forms.IntegerField(label=_('Disk ID'), min_value=DISK_ID_MIN, max_value=max_disks,
                                                    required=True,
                                                    widget=forms.TextInput(
                                                        attrs={'class': 'uneditable-input narrow',
                                                               'required': 'required', 'disabled': 'disabled'}
                                                    ))

    def _initial_data(self, request, vm):
        return get_vm_define_disk(request, vm, disk_id=int(request.POST['opt-disk-disk_id']) - 1)


class AdminServerDiskSettingsForm(ServerDiskSettingsForm):
    """
    Copy of vm_define_disk serializer (api).
    """
    admin = True

    image = forms.TypedChoiceField(label=_('Image'), required=False, coerce=str, empty_value=None,
                                   widget=DataSelect(label_attr='alias_version',
                                                     attrs={'class': 'narrow input-select2'}))
    # noinspection SpellCheckingInspection
    size = forms.IntegerField(label=_('Size'), max_value=268435456, min_value=0, required=True,
                              help_text=_('Changing disk size of created server is a dangerous operation and '
                                          'can cause data loss!'),
                              widget=forms.TextInput(attrs={'class': 'input-transparent narrow input-mbytes',
                                                            'required': 'required',
                                                            'pattern': '[0-9.]+[BKMGTPEbkmgtpe]?'}))
    boot = forms.BooleanField(label=_('Bootable'), required=False,
                              widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    # refreservation disabled
    # refreservation = forms.IntegerField(label=_('Reservation'), max_value=268435456, min_value=0, required=False,
    #                                    widget=NumberInput(attrs={'class': 'input-transparent narrow'}))
    compression = forms.ChoiceField(label=_('Compression'), choices=Vm.DISK_COMPRESSION, required=False,
                                    widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    zpool = forms.ChoiceField(label=_('Storage'), required=False,
                              widget=forms.Select(attrs={'class': 'narrow input-select2'}))

    def __init__(self, request, vm, *args, **kwargs):
        super(AdminServerDiskSettingsForm, self).__init__(request, vm, *args, **kwargs)
        if vm.is_deployed():
            self.fields['image'].widget.attrs['disabled'] = 'disabled'
            self.fields['zpool'].widget.attrs['class'] += ' disable_created2'
            # Bug #chili-625
            img_inc = [disk['image_uuid'] for disk in vm.json_active_get_disks() if 'image_uuid' in disk]
        else:
            img_inc = None

        if vm.is_hvm():
            images = [('', _('(none)'))]
            if vm.is_bhyve():
                self.max_disks = DISK_ID_MAX_BHYVE
            else:
                self.max_disks = DISK_ID_MAX
            self.fields['zpool'].help_text = _('Setting first disk storage to different value than '
                                               'server settings storage (%s) is not recommended.') % vm.zpool
        else:
            del self.fields['boot']
            self.fields['size'].required = False
            images = []
            if vm.is_deployed():
                self.max_disks = 0  # Disable creating of new disks if zone is deployed
            else:
                self.max_disks = DISK_ID_MAX_OS

        images.extend([(i.name, i) for i in get_images(request, ostype=vm.ostype, include=img_inc)])
        self.fields['image'].choices = images
        self.fields['zpool'].choices = get_zpools(request).values_list('zpool', 'storage__alias').distinct()

    def _final_data(self, data=None):
        # noinspection PyProtectedMember
        data = super(AdminServerDiskSettingsForm, self)._final_data(data=data)

        try:  # Remove refreservation if not set
            if data['refreservation'] in (None, ''):
                del data['refreservation']
        except KeyError:
            pass

        if self.cleaned_data['disk_id'] > 1:  # Remove image for non-primary disks
            try:
                del data['image']
            except KeyError:
                pass

            if not self._obj.is_hvm():  # Also remove size and zpool for OS zones
                try:
                    del data['size']
                except KeyError:
                    pass
                try:
                    del data['zpool']
                except KeyError:
                    pass

        return data


class ServerNicSettingsForm(SerializerForm):
    """
    Partial copy of vm_define_nic serializer (api).
    """
    admin = False
    _api_call = vm_define_nic

    nic_id = forms.IntegerField(label=_('Nic ID'), min_value=NIC_ID_MIN, max_value=NIC_ID_MAX, required=True,
                                widget=forms.TextInput(attrs={'class': 'uneditable-input narrow',
                                                              'required': 'required', 'disabled': 'disabled'}))
    model = forms.ChoiceField(label=_('Model'), choices=Vm.NIC_MODEL, required=False,
                              widget=forms.Select(attrs={'class': 'narrow input-select2'}))

    def __init__(self, request, vm, *args, **kwargs):
        super(ServerNicSettingsForm, self).__init__(request, vm, *args, **kwargs)

        # only KVM has multiple vnic models
        if not vm.is_kvm():
            del self.fields['model']

    def _initial_data(self, request, vm):
        return get_vm_define_nic(request, vm, nic_id=int(request.POST['opt-nic-nic_id']) - 1)


class AdminServerNicSettingsForm(ServerNicSettingsForm):
    """
    Copy of vm_define_nic serializer (api).
    """
    admin = True

    net = forms.ChoiceField(label=_('Network'), required=True,
                            widget=DataSelect(attrs={'class': 'narrow input-select2', 'required': 'required'}))
    ip = forms.GenericIPAddressField(label=_('IP Address'), required=False, protocol='ipv4',
                                     widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                                   'placeholder': _('Automatic allocation')}))
    dns = forms.BooleanField(label=_('Create DNS?'), required=False,
                             help_text=_("Create a DNS A record for VM's FQDN?"),
                             widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    monitoring = forms.BooleanField(label=_('Use for monitoring?'), required=False,
                                    help_text=_("Use this NIC's IP address for external monitoring."),
                                    widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    mac = forms.CharField(label=_('MAC Address'), required=False, max_length=20,
                          help_text=_('If left empty, a MAC address will be generated automatically.'),
                          widget=forms.TextInput(attrs={'class': 'input-transparent narrow'}))
    primary = forms.BooleanField(label=_('Primary NIC?'), required=False,
                                 help_text=_("Use this NIC's gateway as VM's default gateway."),
                                 widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    use_net_dns = forms.BooleanField(label=_('Set DNS resolvers from network\'s configuration?'), required=False,
                                     help_text=_("If checked, then the virtual server inherits DNS resolvers from "
                                                 "network's configuration, otherwise the virtual datacenter resolvers "
                                                 "are used."),
                                     widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    allow_dhcp_spoofing = forms.BooleanField(label=_('Allow DHCP Spoofing?'), required=False,
                                             help_text=_('Allow packets required for DHCP server.'),
                                             widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    allow_ip_spoofing = forms.BooleanField(label=_('Allow IP Spoofing?'), required=False,
                                           help_text=_("Allow sending and receiving packets for IP addresses other "
                                                       "than specified in NIC's IP address field."),
                                           widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    allow_mac_spoofing = forms.BooleanField(label=_('Allow MAC Spoofing?'), required=False,
                                            help_text=_("Allow sending packets with MAC addresses other than specified "
                                                        "in NIC's MAC address field."),
                                            widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    allow_restricted_traffic = forms.BooleanField(label=_('Allow Restricted Traffic?'), required=False,
                                                  help_text=_('Allow sending packets that are not IPv4, IPv6, or ARP.'),
                                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))

    def __init__(self, request, vm, *args, **kwargs):
        super(AdminServerNicSettingsForm, self).__init__(request, vm, *args, **kwargs)
        if vm.is_deployed():
            self.fields['mac'].widget.attrs['class'] += ' disable_created'
            # Bug #chili-625
            net_inc = [nic['network_uuid'] for nic in vm.json_active_get_nics() if 'network_uuid' in nic]
        else:
            net_inc = None

        self.max_nics = NIC_ID_MAX
        self.fields['net'].choices = [(i.name, i) for i in get_subnets(request, include=net_inc)]
        self.fields['use_net_dns'].help_text += _(' Current VM configuration: %(resolvers)s') % {
            'resolvers': ', '.join(vm.resolvers),
        }

        if not request.user.is_staff:
            self.fields['allow_dhcp_spoofing'].widget.attrs['disabled'] = 'disabled'
            self.fields['allow_ip_spoofing'].widget.attrs['disabled'] = 'disabled'
            self.fields['allow_mac_spoofing'].widget.attrs['disabled'] = 'disabled'
            self.fields['allow_restricted_traffic'].widget.attrs['disabled'] = 'disabled'

    def _initial_data(self, request, vm):
        ret = super(AdminServerNicSettingsForm, self)._initial_data(request, vm)
        # We need string representation of arrays
        # if 'allowed_ips' in ret:
        #    ret['allowed_ips'] = tags_to_string(ret['allowed_ips'])

        # "Blankify" empty mac address
        if 'mac' in ret:
            ret['mac'] = self._blank(ret['mac'])

        return ret

    def _input_data(self):
        # noinspection PyProtectedMember
        data = super(AdminServerNicSettingsForm, self)._input_data()

        # When IP is blank it should be rather null in when comparing to serializer value
        if 'ip' in data:
            data['ip'] = self._null(data['ip'])

        return data


class UploadFileForm(forms.Form):
    import_file = forms.FileField(label=_('File with servers'), required=True)

    FILE_CONTENT_TYPE_WHITELIST = (
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'application/vms.ms-excel',
        'application/msexcel',
        # 'text/csv'
        # 'application/vnd.oasis.opendocument.spreadsheet'
    )

    def clean_import_file(self):
        import_file = self.cleaned_data.get('import_file')

        if import_file:
            if import_file.content_type not in self.FILE_CONTENT_TYPE_WHITELIST:
                raise forms.ValidationError(_('File type is not supported'))

        return import_file


class SnapshotDefineForm(SerializerForm, HostnameForm):
    """
    Create or update snapshot definition.
    """
    _api_call = vm_define_snapshot

    name = forms.RegexField(label=_('Name'), regex=r'^[A-Za-z0-9][A-Za-z0-9._-]*$', required=True,
                            max_length=8, min_length=1,
                            widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                          'required': 'required', 'pattern': '[A-Za-z0-9._-]+'}))
    disk_id = forms.TypedChoiceField(label=_('Disk ID'), required=True, coerce=int,
                                     widget=forms.Select(attrs={'class': 'input-select2 narrow',
                                                                'required': 'required'}))
    schedule = forms.CharField(label=_('Schedule'), required=True, max_length=100,
                               help_text=_('CRON format (<minute> <hour> <day of month> <month> <day of week>). '
                                           'Use your local time for the hour field '
                                           '(it will be internally converted into UTC).'),
                               widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                             'required': 'required'}))
    retention = forms.IntegerField(label=_('Retention'), max_value=65536, min_value=0, required=True,
                                   help_text=_('Maximum number of snapshots to keep.'),
                                   widget=NumberInput(attrs={'class': 'input-transparent narrow',
                                                             'required': 'required'}))
    active = forms.BooleanField(label=_('Active?'), required=False,
                                widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    desc = forms.RegexField(label=_('Description'), regex=r'^[^<>%\$&;\'"]*$', max_length=128, required=False,
                            widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))
    fsfreeze = forms.BooleanField(label=_('Freeze filesystem?'), required=False,
                                  help_text=_('Create application-consistent snapshot; '
                                              'Requires QEMU Guest Agent.'),
                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))

    def __init__(self, request, vm, *args, **kwargs):
        super(SnapshotDefineForm, self).__init__(request, vm, *args, **kwargs)
        self.fields['disk_id'].choices = vm_disk_id_choices(vm)

    def clean_schedule(self):
        """Time in schedule in templates is timezone aware. Change to UTC."""
        data = self.cleaned_data.get('schedule')

        try:
            schedule = data.split()
            hour = schedule[1]
            if '*' in hour:
                raise IndexError
        except IndexError:
            return data

        tz = timezone.get_current_timezone()
        now_local = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(tz)

        def to_utc(match):
            num = int(match.group(0))
            now = now_local.replace(hour=num)
            return str(pytz.utc.normalize(now).hour)

        try:
            schedule[1] = re.sub(r'(\d+)', to_utc, hour)
        except ValueError:
            return data

        return ' '.join(schedule)

    def _initial_data(self, request, vm):
        snapname = request.POST.get('name')
        disk_id = request.POST.get('disk_id')
        res = self.api_call('get', vm, request, args=(vm.hostname, snapname), data={'disk_id': disk_id})

        return res.data['result']

    def _final_data(self, data=None):
        # noinspection PyProtectedMember
        fd = super(SnapshotDefineForm, self)._final_data(data=data)
        # Always include disk_id (required parameter in api call)
        fd['disk_id'] = self.cleaned_data['disk_id']

        return fd


class CreateSnapshotDefineForm(SnapshotDefineForm):
    """
    Create snapshot definition.
    """

    def __init__(self, request, vm, *args, **kwargs):
        super(CreateSnapshotDefineForm, self).__init__(request, vm, *args, **kwargs)
        from api.vm.snapshot.serializers import define_schedule_defaults
        schret = define_schedule_defaults('daily')
        self.fields['name'].widget.attrs['placeholder'] = 'daily'
        self.fields['schedule'].widget.attrs['placeholder'] = schret.get('schedule', '')
        self.fields['retention'].widget.attrs['placeholder'] = schret.get('retention', '')


class UpdateSnapshotDefineForm(SnapshotDefineForm):
    """
    Update snapshot definition.
    """

    def __init__(self, *args, **kwargs):
        super(UpdateSnapshotDefineForm, self).__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['disabled'] = 'disabled'
        self.fields['name'].widget.attrs['class'] += ' uneditable-input'
        self.fields['disk_id'].widget.attrs['disabled'] = 'disabled'


class SnapshotForm(HostnameForm):
    """
    Form for creating new disk snapshots of VM.
    """
    name = forms.RegexField(label=_('Snapshot Name'), regex=r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', required=True,
                            max_length=24, min_length=1,
                            widget=forms.TextInput(attrs={'placeholder': _('backup1'),
                                                          'class': 'input-transparent narrow',
                                                          'required': 'required', 'pattern': '[A-Za-z0-9._-]+'}))
    disk_id = forms.TypedChoiceField(label=_('Disk ID'), required=True, coerce=int,
                                     widget=forms.Select(attrs={'class': 'input-select2 narrow',
                                                                'required': 'required'}))
    note = forms.RegexField(label=_('Note'), regex=r'^[^<>%\$&;\'"]*$', help_text=_('Optional snapshot comment.'),
                            max_length=128, required=False,
                            widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))

    def __init__(self, vm, *args, **kwargs):
        super(SnapshotForm, self).__init__(*args, **kwargs)
        self._vm = vm
        self.fields['disk_id'].choices = vm_disk_id_choices(vm)

    def _get_real_disk_id(self):
        return Snapshot.get_disk_id(self._vm, self.cleaned_data['disk_id'])


class CreateSnapshotForm(SnapshotForm):
    disk_all = forms.BooleanField(label=_('All disks?'), required=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    fsfreeze = forms.BooleanField(label=_('Freeze filesystem?'), required=False,
                                  help_text=_('Create application-consistent snapshot; '
                                              'Requires QEMU Guest Agent.'),
                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))

    def clean(self):
        cleaned_data = super(CreateSnapshotForm, self).clean()
        name = cleaned_data.get('name')
        disk_id = cleaned_data.get('disk_id')

        if not (name and disk_id):
            return cleaned_data

        snapf = {'name': name, 'vm': self._vm}

        if cleaned_data.get('disk_all'):
            snapc = len(self._vm.json_active_get_disks())
        else:
            snapf['disk_id'] = self._get_real_disk_id()
            snapc = 1

        if Snapshot.objects.filter(**snapf).exists():
            self._errors['name'] = self.error_class([_('Snapshot name is already used')])
            del cleaned_data['name']

        try:
            limit = int(self._vm.json['internal_metadata']['snapshot_limit_manual'])
        except (TypeError, KeyError, IndexError):
            pass
        else:
            total = Snapshot.objects.filter(vm=self._vm, type=Snapshot.MANUAL).count()
            if total + snapc > limit:
                raise forms.ValidationError(_('Snapshot limit reached'))

        return cleaned_data


class UpdateSnapshotForm(SnapshotForm):
    def __init__(self, *args, **kwargs):
        super(UpdateSnapshotForm, self).__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['disabled'] = 'disabled'
        self.fields['name'].widget.attrs['class'] += ' uneditable-input'
        self.fields['disk_id'].widget.attrs['disabled'] = 'disabled'

    def get_snapshot(self):
        try:
            return Snapshot.objects.get(vm=self._vm, name=self.cleaned_data['name'],
                                        disk_id=self._get_real_disk_id())
        except Snapshot.DoesNotExist:
            return None

    def save(self, snap):
        if snap.note == self.cleaned_data['note']:
            return False

        snap.note = self.cleaned_data['note']
        snap.save(update_fields=('note', 'changed'))
        return True


class BackupDefineForm(SerializerForm, HostnameForm):
    """
    Create or update backup definition.
    """
    _api_call = vm_define_backup

    type = forms.TypedChoiceField(label=_('Backup type'), required=True, choices=BackupDefine.TYPE, coerce=int,
                                  widget=forms.Select(attrs={'class': 'narrow input-select2 disable_create2',
                                                             'required': 'required'}))
    node = forms.ChoiceField(label=_('Backup Node'), required=True,
                             widget=forms.Select(attrs={'class': 'narrow input-select2', 'required': 'required'}))
    zpool = forms.ChoiceField(label=_('Storage'), required=True,
                              widget=forms.Select(attrs={'class': 'narrow input-select2', 'required': 'required'}))
    compression = forms.TypedChoiceField(label=_('Compression'), choices=BackupDefine.COMPRESSION, required=True,
                                         coerce=int, widget=forms.Select(attrs={'class': 'narrow input-select2',
                                                                                'required': 'required'}))
    bwlimit = forms.IntegerField(label=_('Bandwidth limit'), required=False,
                                 help_text=_('Optional transfer rate limit in bytes.'),
                                 widget=NumberInput(attrs={'class': 'input-transparent narrow'}))

    def __init__(self, request, vm, *args, **kwargs):
        super(BackupDefineForm, self).__init__(request, vm, *args, **kwargs)
        self.fields['retention'].help_text = _('Maximum number of backups to keep.')
        self.fields['node'].choices = get_nodes(request, is_backup=True).values_list('hostname', 'hostname')
        self.fields['zpool'].choices = get_zpools(request).filter(node__is_backup=True) \
            .values_list('zpool', 'storage__alias').distinct()


class CreateBackupDefineForm(BackupDefineForm, CreateSnapshotDefineForm):
    pass


class UpdateBackupDefineForm(BackupDefineForm, UpdateSnapshotDefineForm):
    def __init__(self, *args, **kwargs):
        super(UpdateBackupDefineForm, self).__init__(*args, **kwargs)
        self.fields['type'].widget.attrs['disabled'] = 'disabled'


class BackupForm(HostnameForm):
    """
    Form for creating or updating VM backups.
    """
    note = forms.RegexField(label=_('Note'), regex=r'^[^<>%\$&;\'"]*$', help_text=_('Optional backup comment.'),
                            max_length=128, required=False,
                            widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))

    def __init__(self, vm, *args, **kwargs):
        self._vm = vm
        super(BackupForm, self).__init__(*args, **kwargs)


class CreateBackupForm(BackupForm):
    """
    Backup now - run definition.
    """
    define = forms.ChoiceField(label=_('Definition'), required=True,
                               widget=forms.Select(attrs={'class': 'input-select2 narrow', 'required': 'required'}))

    def __init__(self, vm, bkpdefs, *args, **kwargs):
        super(CreateBackupForm, self).__init__(vm, *args, **kwargs)
        # Displays node hostname (complete web_data)
        disks = vm.json_active_get_disks()

        def get_disk(index):
            try:
                return disks[index]
            except IndexError:
                return {'size': 0}

        self.fields['define'].choices = [('%s@%s' % (i.name,
                                                     i.array_disk_id),
                                          '%s - %s' % (i.name,
                                                       disk_id_option(i.array_disk_id, get_disk(i.array_disk_id - 1))))
                                         for i in bkpdefs]


class UpdateBackupForm(BackupForm):
    """
    Update backup note.
    """
    disk_id = forms.TypedChoiceField(label=_('Disk ID'), required=True, coerce=int,
                                     widget=forms.Select(attrs={'class': 'input-select2 narrow',
                                                                'disabled': 'disabled'}))
    name = forms.CharField(label=_('Backup Name'), required=True, max_length=24,
                           widget=forms.TextInput(attrs={'class': 'input-transparent narrow uneditable-input',
                                                         'disabled': 'disabled'}))

    def __init__(self, *args, **kwargs):
        super(UpdateBackupForm, self).__init__(*args, **kwargs)
        if self._vm:
            self.fields['disk_id'].choices = vm_disk_id_choices(self._vm)
        else:
            # we use DISK_ID_MAX_BHYVE here because it's bigger than DISK_ID_MAX
            self.fields['disk_id'].choices = [(i, _('Disk') + ' %d' % i) for i in range(1, DISK_ID_MAX_BHYVE + 1)]

    def _get_real_disk_id(self):
        return Backup.get_disk_id(self._vm, self.cleaned_data['disk_id'])

    def get_backup(self):
        try:
            return Backup.objects.get(vm=self._vm, name=self.cleaned_data['name'],
                                      disk_id=self._get_real_disk_id())
        except Backup.DoesNotExist:
            return None

    def save(self, bkp):
        if bkp.note == self.cleaned_data['note']:
            return False

        bkp.note = self.cleaned_data['note']
        bkp.save(update_fields=('note', 'changed'))
        return True


class RestoreBackupForm(forms.Form):
    """
    Target hostname and target disk_id attributes of vm_backup restore.
    """
    target_hostname = forms.ChoiceField(label=_('Restore to Server'), required=True,
                                        widget=MetaDataSelect(attrs={'class': 'narrow input-select2'}))
    target_disk_id = forms.TypedChoiceField(label=_('Restore to Disk'), required=True, coerce=int,
                                            widget=forms.Select(attrs={'class': 'input-select2 narrow',
                                                                       'required': 'required'}))

    def __init__(self, vms, *args, **kwargs):
        super(RestoreBackupForm, self).__init__(*args, **kwargs)

        # noinspection PyShadowingNames
        def disks(vm):
            return [(i + 1, disk_id_option(i + 1, disk), int(disk['size']))
                    for i, disk in enumerate(vm.json_active_get_disks())]

        # Locked VMs are marked as disabled in drop down list
        # Disks metadata are used to render target_disk_id drop down list
        self.fields['target_hostname'].choices = [((vm.hostname, {'disks': disks(vm)},
                                                    {'disabled': 'disabled'} if vm.locked else {}), vm.hostname)
                                                  for vm in vms if vm.is_deployed()]


class UndoSettingsForm(SerializerForm):
    """
    For for calling vm_define_revert.
    """
    _api_call = vm_define_revert


class SnapshotImageForm(HostnameForm, _ImageForm):
    """
    Create Image from snapshot.
    """
    _api_call = image_snapshot

    snapname = forms.CharField(label=_('Snapshot Name'), required=False,
                               widget=forms.TextInput(attrs={'class': 'input-transparent narrow uneditable-input',
                                                             'required': 'required', 'disabled': 'disabled'}))
    disk_id = forms.TypedChoiceField(label=_('Disk ID'), required=False, coerce=int,
                                     widget=forms.Select(attrs={'class': 'input-select2 narrow',
                                                                'required': 'required', 'disabled': 'disabled'}))

    def __init__(self, vm, *args, **kwargs):
        super(SnapshotImageForm, self).__init__(*args, **kwargs)
        self._vm = vm
        self.fields['disk_id'].choices = vm_disk_id_choices(vm)
