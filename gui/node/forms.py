from operator import and_
from functools import reduce
from django import forms
from django.core.validators import RegexValidator
from django.db.models import Q, Count
from django.utils.translation import ugettext_lazy as _
from django.template.defaultfilters import filesizeformat
from django.http import Http404
from django.utils.six import PY3

from api.mon import MonitoringBackend
from api.vm.utils import get_owners
from api.dc.utils import get_dcs
from api.node.define.views import node_define
from api.node.storage.views import node_storage
from gui.forms import SerializerForm
from gui.fields import ArrayField
from gui.widgets import ArrayWidget
from gui.vm.forms import UpdateBackupForm as _UpdateBackupForm
from vms.models import Node, Storage, Backup, Image, Vm

if PY3:
    t_long = int
else:
    t_long = long


class NodeForm(SerializerForm):
    """
    Update compute node settings.
    """
    _api_call = node_define

    hostname = forms.CharField(label=_('Hostname'),
                               widget=forms.TextInput(attrs={'class': 'input-transparent narrow uneditable-input',
                                                             'disabled': 'disabled'}))
    owner = forms.ChoiceField(label=_('Owner'),
                              widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    status = forms.TypedChoiceField(label=_('Status'), choices=Node.STATUS, coerce=int,
                                    widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    is_compute = forms.BooleanField(label=_('Compute?'), required=False,
                                    widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    is_backup = forms.BooleanField(label=_('Backup?'), required=False,
                                   widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    note = forms.CharField(label=_('Note'), help_text=_('Custom text information about this compute node, with markdown'
                                                        ' support.'),
                           required=False,
                           widget=forms.Textarea(attrs={
                               'class': 'input-transparent small',
                               'rows': 5})
                           )
    cpu_coef = forms.DecimalField(label=_('CPUs coefficient'), max_digits=4, decimal_places=2,
                                  help_text=_('Coefficient for calculating the the total number of virtual CPUs.'),
                                  widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                                'required': 'required'}))
    ram_coef = forms.DecimalField(label=_('RAM coefficient'), max_digits=4, decimal_places=2,
                                  help_text=_('Coefficient for calculating the maximum amount of memory '
                                              'for virtual machines.'),
                                  widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                                'required': 'required'}))

    monitoring_templates = ArrayField(label=_('Monitoring templates'), required=False, tags=True,
                                      help_text=_('Comma-separated list of custom monitoring templates.'),
                                      widget=ArrayWidget(tags=True, escape_space=False,
                                                         attrs={'class': 'tags-select2 narrow',
                                                                'data-tags-type': 'mon_templates',
                                                                'data-tags-api-call': 'mon_node_template_list'}))
    monitoring_hostgroups = ArrayField(label=_('Monitoring hostgroups'), required=False, tags=True,
                                       help_text=_('Comma-separated list of custom monitoring hostgroups.'),
                                       validators=[
                                           RegexValidator(regex=MonitoringBackend.VALID_MONITORING_HOSTGROUP_REGEX)],
                                       widget=ArrayWidget(tags=True, escape_space=False,
                                                          attrs={'class': 'tags-select2 narrow',
                                                                 'data-tags-type': 'mon_hostgroups',
                                                                 'data-tags-api-call': 'mon_node_hostgroup_list'}))

    def __init__(self, request, node, *args, **kwargs):
        super(NodeForm, self).__init__(request, node, *args, **kwargs)
        self.fields['owner'].choices = get_owners(request).values_list('username', 'username')

        if node.is_unlicensed():
            self.fields['status'].choices = Node.STATUS_DB
            self.fields['status'].widget.attrs['disabled'] = 'disabled'
        elif node.is_unreachable():
            self.fields['status'].choices = Node.STATUS_DB[:-1]
            self.fields['status'].widget.attrs['disabled'] = 'disabled'

    def _initial_data(self, request, obj):
        return obj.web_data


class NodeStorageForm(SerializerForm):
    """
    Create or update node storage.
    """
    _api_call = node_storage

    node = forms.CharField(label=_('Node'),
                           widget=forms.TextInput(attrs={'class': 'input-transparent narrow uneditable-input',
                                                         'disabled': 'disabled'}))
    zpool = forms.ChoiceField(label=_('Zpool'),
                              widget=forms.Select(attrs={'class': 'narrow input-select2 disable_created2'}))
    alias = forms.CharField(label=_('Alias'), required=True, max_length=32,
                            widget=forms.TextInput(attrs={'class': 'input-transparent narrow', 'required': 'required'}))
    type = forms.TypedChoiceField(label=_('Type'), required=False, coerce=int, choices=Storage.TYPE,
                                  widget=forms.Select(attrs={'class': 'input-select2 narrow'}))
    owner = forms.ChoiceField(label=_('Owner'), required=False,
                              widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    access = forms.TypedChoiceField(label=_('Access'), required=False, coerce=int, choices=Storage.ACCESS,
                                    widget=forms.Select(attrs={'class': 'input-select2 narrow'}))
    desc = forms.CharField(label=_('Description'), max_length=128, required=False,
                           widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))
    size_coef = forms.DecimalField(label=_('Size coefficient'), max_digits=4, decimal_places=2,
                                   help_text=_('Coefficient for calculating the maximum amount of '
                                               'disk space for virtual machines.'),
                                   widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                                 'required': 'required'}))

    def __init__(self, request, node, ns, *args, **kwargs):
        super(NodeStorageForm, self).__init__(request, ns, *args, **kwargs)
        self.fields['owner'].choices = get_owners(request).values_list('username', 'username')
        node_zpools = node.zpools
        zpools = [(k, '%s (%s)' % (k, filesizeformat(int(v['size']) * 1048576))) for k, v in node_zpools.items()]

        # Add zpools for NodeStorage objects that have vanished from compute node (Issue #chili-27)
        for zpool in node.nodestorage_set.exclude(zpool__in=node_zpools.keys()).values_list('zpool', flat=True):
            zpools.append((zpool, '%s (???)' % zpool))

        self.fields['zpool'].choices = zpools

    def _initial_data(self, request, obj):
        data = obj.web_data
        data['size_coef'] = obj.storage.size_coef
        return data


class UpdateBackupForm(_UpdateBackupForm):
    """
    Update backup note from node perspective.
    """
    # noinspection PyMethodOverriding
    def get_backup(self, node):
        try:
            return Backup.objects.get(vm_hostname=self.cleaned_data['hostname'], name=self.cleaned_data['name'],
                                      vm_disk_id=self.cleaned_data['disk_id'] - 1, node=node)
        except Backup.DoesNotExist:
            return None


class NodeStorageImageForm(forms.Form):
    """
    Import or delete image into/from node storage.
    """
    node = forms.CharField(label=_('Node'),
                           widget=forms.TextInput(attrs={'class': 'input-transparent narrow uneditable-input',
                                                         'disabled': 'disabled'}))
    zpool = forms.ChoiceField(label=_('Storage'),
                              widget=forms.Select(attrs={'class': 'narrow input-select2', 'disabled': 'disabled'}))
    name = forms.ChoiceField(label=_('Image'),
                             widget=forms.Select(attrs={'class': 'narrow input-select2 disable_created2'}))

    def __init__(self, ns, *args, **kwargs):
        super(NodeStorageImageForm, self).__init__(*args, **kwargs)
        self.fields['zpool'].choices = [(ns.zpool, ns.alias)]
        self.fields['name'].choices = [(i.name, i.alias_version)
                                       for i in Image.objects.only('name', 'alias', 'version').all()]


class BackupFilterForm(forms.Form):
    """
    Filter backups on backup node.
    """
    dc = forms.ChoiceField(label=_('Datacenter'), required=False,
                           widget=forms.Select(attrs={'class': 'fill-up input-navigation select-transparent'}))
    hostname = forms.ChoiceField(label=_('Server'), required=False,
                                 widget=forms.Select(attrs={'class': 'fill-up input-navigation select-transparent'}))
    type = forms.ChoiceField(label=_('Backup type'), required=False, choices=(('', _('Type (all)')),) + Backup.TYPE,
                             widget=forms.Select(attrs={'class': 'fill-up input-navigation select-transparent'}))
    status = forms.ChoiceField(label=_('Status'), required=False, choices=(('', _('Status (all)')),) + Backup.STATUS,
                               widget=forms.Select(attrs={'class': 'fill-up input-navigation select-transparent'}))
    min_size = forms.IntegerField(label=_('Larger than'), required=False,
                                  widget=forms.TextInput(attrs={'class': 'fill-up input-navigation input-transparent',
                                                                'placeholder': _('Larger than (MB)')}))
    max_size = forms.IntegerField(label=_('Smaller than'), required=False,
                                  widget=forms.TextInput(attrs={'class': 'fill-up input-navigation input-transparent',
                                                                'placeholder': _('Smaller than (MB)')}))
    created_since = forms.DateField(label=_('Created since'), required=False, input_formats=('%Y-%m-%d',),
                                    widget=forms.DateInput(format='%Y-%m-%d',
                                                           attrs={'placeholder': _('Created since'),
                                                                  'class': 'fill-up input-navigation input-transparent '
                                                                  'input-date'}))
    created_until = forms.DateField(label=_('Created until'), required=False, input_formats=('%Y-%m-%d',),
                                    widget=forms.DateInput(format='%Y-%m-%d',
                                                           attrs={'placeholder': _('Created until'),
                                                                  'class': 'fill-up input-navigation input-transparent '
                                                                  'input-date'}))

    def __init__(self, request, node, data, **kwargs):
        super(BackupFilterForm, self).__init__(data, **kwargs)

        vms = list(node.backup_set.values('vm__hostname', 'vm__alias')
                                  .annotate(bkps=Count('id')).order_by('vm__hostname'))

        vms_list = [('', _('Server (all)'))]

        if vms and not vms[-1]['vm__hostname']:  # We have backups without VM
            no_vm = vms.pop()
            vms_list.append(('novm', _('(no server) (%s)') % no_vm['bkps']))

        self.qs = {}
        self.vm = None
        self.no_vm = False
        self.all_vm = True
        self.fields['dc'].choices = [('', _('Datacenter (all)'))] + list(get_dcs(request).values_list('name', 'alias'))
        self.fields['hostname'].choices = vms_list + [(vm['vm__hostname'], '%s (%s)' % (vm['vm__hostname'], vm['bkps']))
                                                      for vm in vms]

    def get_filters(self):
        data = self.cleaned_data
        query = []

        hostname = data.get('hostname')
        if hostname:
            self.all_vm = False

            if hostname == 'novm':
                self.no_vm = True
                query.append(Q(vm__isnull=True))
            else:
                try:
                    self.vm = Vm.objects.select_related('dc').get(hostname=hostname)
                except Vm.DoesNotExist:
                    raise Http404
                else:
                    query.append(Q(vm__hostname=hostname))

        dc = data.get('dc')
        if dc:
            query.append(Q(dc__name=dc))

        _type = data.get('type')
        if _type:
            query.append(Q(type=_type))

        status = data.get('status')
        if status:
            query.append(Q(status=status))

        min_size = data.get('min_size')
        if min_size:
            query.append(Q(size__gte=t_long(min_size) * 1048576))

        max_size = data.get('max_size')
        if max_size:
            query.append(Q(size__lte=t_long(max_size) * 1048576))

        created_since = data.get('created_since')
        if created_since:
            query.append(Q(created__gte=created_since))

        created_until = data.get('created_until')
        if created_until:
            query.append(Q(created__lte=created_until))

        if query:
            return reduce(and_, query)
        else:
            return None
