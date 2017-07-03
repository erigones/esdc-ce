from django import forms
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from frozendict import frozendict

from vms.models import Dc, Image
from api.dc.base.views import dc_manage, dc_settings
from api.dc.base.serializers import DcSettingsSerializer, DefaultDcSettingsSerializer
from api.vm.utils import get_vms, get_owners, get_images, get_subnets, get_zpools
from api.mon import get_monitoring
from gui.forms import SerializerForm
from gui.fields import ArrayAreaField
from gui.widgets import ArrayAreaWidget
from gui.models import Role


class DcForm(SerializerForm):
    """
    Create or update Datacenter by calling dc_manage (available only for staff users).
    """
    _api_call = dc_manage

    name = forms.CharField(label=_('Name'), max_length=16, required=True,
                           widget=forms.TextInput(attrs={'class': 'input-transparent narrow disable_created',
                                                         'required': 'required', 'pattern': '[A-Za-z0-9:\._-]+'}))
    alias = forms.CharField(label=_('Alias'), required=True, max_length=32,
                            widget=forms.TextInput(attrs={'class': 'input-transparent narrow', 'required': 'required'}))
    site = forms.CharField(label=_('Site Hostname'), max_length=260, required=True,
                           widget=forms.TextInput(attrs={'class': 'input-transparent narrow', 'required': 'required',
                                                         'pattern': '[a-z0-9\.-]+'}))
    owner = forms.ChoiceField(label=_('Owner'), required=False,
                              widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    access = forms.TypedChoiceField(label=_('Access'), required=False, coerce=int, choices=Dc.ACCESS,
                                    widget=forms.Select(attrs={'class': 'input-select2 narrow'}))
    groups = forms.MultipleChoiceField(label=_('Groups'), required=False,
                                       widget=forms.SelectMultiple(attrs={'class': 'narrow input-select2 '
                                                                                   'tags-select2'}))
    desc = forms.CharField(label=_('Description'), max_length=128, required=False,
                           widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))

    not_advanced = frozenset(('name', 'alias', 'site', 'owner', 'access', 'groups', 'desc'))

    def __init__(self, request, dc, *args, **kwargs):
        super(DcForm, self).__init__(request, dc, *args, **kwargs)
        self.fields['owner'].choices = get_owners(request, all=True).values_list('username', 'username')
        self.fields['groups'].choices = Role.objects.all().values_list('name', 'alias')

    def _initial_data(self, request, obj):
        return obj.web_data


select_widget = {'class': 'narrow input-select2'}
mon_templates_widget = {'class': 'table-tags-select2', 'data-tags-type': 'mon_templates'}
mon_hostgroups_widget = {'class': 'table-tags-select2', 'data-tags-type': 'mon_hostgroups'}


class DcSettingsForm(SerializerForm):
    """
    Update Datacenter settings by calling dc_settings.
    """
    _changed_data = None
    _serializer = DcSettingsSerializer
    _api_call = dc_settings
    _ignore_empty_fields = frozenset(['VMS_DISK_IMAGE_ZONE_DEFAULT', 'VMS_NET_DEFAULT', 'VMS_STORAGE_DEFAULT'])
    _exclude_fields = frozenset(['VMS_NODE_SSH_KEYS_SYNC'])
    _custom_fields = frozendict({
        'VMS_VM_DOMAIN_DEFAULT': forms.ChoiceField,
        'VMS_DISK_IMAGE_DEFAULT': forms.ChoiceField,
        'VMS_DISK_IMAGE_ZONE_DEFAULT': forms.ChoiceField,
        'VMS_IMAGE_SOURCES': ArrayAreaField,
        'VMS_IMAGE_VM': forms.ChoiceField,
        'VMS_NET_DEFAULT': forms.ChoiceField,
        'VMS_STORAGE_DEFAULT': forms.ChoiceField,
        'VMS_VM_SSH_KEYS_DEFAULT': ArrayAreaField,
        'VMS_NODE_SSH_KEYS_DEFAULT': ArrayAreaField,
    })
    _custom_widgets = frozendict({
        'VMS_VM_DOMAIN_DEFAULT': forms.Select,
        'VMS_DISK_IMAGE_DEFAULT': forms.Select,
        'VMS_DISK_IMAGE_ZONE_DEFAULT': forms.Select,
        'VMS_IMAGE_SOURCES': ArrayAreaWidget,
        'VMS_IMAGE_VM': forms.Select,
        'VMS_NET_DEFAULT': forms.Select,
        'VMS_STORAGE_DEFAULT': forms.Select,
        'VMS_VM_SSH_KEYS_DEFAULT': ArrayAreaWidget,
        'SITE_SIGNATURE': forms.Textarea,
        'VMS_NODE_SSH_KEYS_DEFAULT': ArrayAreaWidget,
    })
    _custom_widget_attrs = frozendict({
        'VMS_VM_DOMAIN_DEFAULT': select_widget,
        'VMS_DISK_IMAGE_DEFAULT': select_widget,
        'VMS_DISK_IMAGE_ZONE_DEFAULT': select_widget,
        'VMS_IMAGE_VM': select_widget,
        'VMS_NET_DEFAULT': select_widget,
        'VMS_STORAGE_DEFAULT': select_widget,
        'SITE_SIGNATURE': {'rows': 2},
        'VMS_VM_MDATA_DEFAULT': {'data-raw_input_enabled': 'true'},
    })

    not_advanced = frozenset(set(DcSettingsSerializer.modules) - {'VMS_ZONE_ENABLED'} | {'dc'})
    third_party_modules = frozenset(DcSettingsSerializer.third_party_modules)
    third_party_settings = DcSettingsSerializer.third_party_settings
    mon_hostgroup_list_fields = (
        'MON_ZABBIX_HOSTGROUPS_VM',
        'MON_ZABBIX_HOSTGROUPS_VM_ALLOWED',
        'MON_ZABBIX_HOSTGROUPS_NODE',
    )
    mon_template_list_fields = (
        'MON_ZABBIX_TEMPLATES_VM',
        'MON_ZABBIX_TEMPLATES_VM_ALLOWED',
        'MON_ZABBIX_TEMPLATES_VM_NIC',
        'MON_ZABBIX_TEMPLATES_VM_DISK',
        'MON_ZABBIX_TEMPLATES_NODE',
    )
    globals = frozenset()

    def __init__(self, request, obj, *args, **kwargs):
        self._disable_globals = kwargs.pop('disable_globals', False)

        self.table = kwargs.pop('table', False)
        if self.table:
            self._field_text_class = ''

        super(DcSettingsForm, self).__init__(request, obj, *args, **kwargs)

        from pdns.models import Domain
        self.fields['VMS_VM_DOMAIN_DEFAULT'].choices = Domain.objects.exclude(Domain.QServerExclude)\
            .values_list('name', 'name').order_by('name')
        self.fields['VMS_DISK_IMAGE_DEFAULT'].choices = [('', _('(none)'))] + list(get_images(request, ostype=None)
                                                                                   .values_list('name', 'alias'))
        self.fields['VMS_DISK_IMAGE_ZONE_DEFAULT'].choices = list(get_images(request, ostype=Image.SUNOS_ZONE)
                                                                  .values_list('name', 'alias'))
        self.fields['VMS_NET_DEFAULT'].choices = get_subnets(request).values_list('name', 'alias')
        self.fields['VMS_STORAGE_DEFAULT'].choices = get_zpools(request).values_list('zpool', 'storage__alias')\
                                                                        .distinct()
        self.fields['VMS_VM_SNAPSHOT_SIZE_LIMIT'].addon = ' MB'
        self.fields['VMS_VM_SNAPSHOT_SIZE_LIMIT_DEFAULT'].addon = ' MB'
        self.fields['VMS_VM_SNAPSHOT_DC_SIZE_LIMIT'].addon = ' MB'
        self.fields['VMS_VM_BACKUP_DC_SIZE_LIMIT'].addon = ' MB'

    def _build_field(self, name, serializer_field, form_field_class, **form_field_options):
        source = serializer_field.source or name

        # Disable modules which are disabled in local_settings
        # noinspection PyProtectedMember
        if source in self._serializer._override_disabled_ and not getattr(settings, source, False):
            form_field_options['widget'].attrs['disabled'] = 'disabled'

        # Show disabled global settings (only useful for DefaultDcSettingsForm)
        if self._disable_globals and source in self.globals:
            form_field_options['widget'].attrs['disabled'] = 'disabled'
            form_field_options['required'] = False

        if self.table:
            if source in self.mon_hostgroup_list_fields:
                form_field_options['tags'] = True
                form_field_options['widget'].tags = True
                form_field_options['widget'].escape_space = False
                form_field_options['widget'].attrs = mon_hostgroups_widget
            elif source in self.mon_template_list_fields:
                form_field_options['tags'] = True
                form_field_options['widget'].tags = True
                form_field_options['widget'].escape_space = False
                form_field_options['widget'].attrs = mon_templates_widget

        return super(DcSettingsForm, self)._build_field(name, serializer_field, form_field_class, **form_field_options)

    def _initial_data(self, request, obj):
        data = super(DcSettingsForm, self)._initial_data(request, obj)

        if self.table:
            try:
                del data['dc']
            except KeyError:
                pass

        return data

    def _has_changed(self):
        # Save changed data
        ret = super(DcSettingsForm, self)._has_changed()
        self._changed_data = ret

        return ret

    def set_mon_zabbix_server_login_error(self):
        if self._changed_data and 'MON_ZABBIX_SERVER' in self._changed_data:
            return  # Do not set error if setting has changed

        zx = get_monitoring(self._request.dc)
        zx_error = zx.ezx.login_error

        if zx_error:
            self.set_error('MON_ZABBIX_SERVER', zx_error)


class DefaultDcSettingsForm(DcSettingsForm):
    """
    Update default Datacenter settings by calling dc_settings.
    """
    _serializer = DefaultDcSettingsSerializer
    globals = DefaultDcSettingsSerializer.get_global_settings()

    default_dc_third_party_modules = set(DefaultDcSettingsSerializer.default_dc_third_party_modules)
    default_dc_third_party_settings = DefaultDcSettingsSerializer.default_dc_third_party_settings

    def __init__(self, request, *args, **kwargs):
        super(DefaultDcSettingsForm, self).__init__(request, *args, **kwargs)
        all_vms = get_vms(request, dc_bound=False).values_list('uuid', 'hostname')
        self.fields['VMS_IMAGE_VM'].choices = [('', _('(none)'))] + list(all_vms)
