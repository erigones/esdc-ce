from django.utils.translation import ugettext_lazy as _
from django.core import validators

from vms.models import BackupDefine, Backup, Node, NodeStorage
from api import serializers as s
from api.vm.utils import get_nodes, get_zpools
# noinspection PyProtectedMember
from api.vm.snapshot.serializers import DISK_ID_MIN, DISK_ID_MAX, RETENTION_MAX, RETENTION_MIN, _HideNodeSerializer


class BackupDefineSerializer(_HideNodeSerializer):
    """
    vms.models.BackupDefine
    """
    _model_ = BackupDefine
    _update_fields_ = ('type', 'desc', 'node', 'zpool', 'bwlimit', 'active', 'schedule', 'retention', 'compression')
    _default_fields_ = ('hostname', 'name', 'disk_id')

    hostname = s.CharField(source='vm.hostname', read_only=True)
    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=8, min_length=1)
    disk_id = s.IntegerField(source='array_disk_id', max_value=DISK_ID_MAX, min_value=DISK_ID_MIN)
    type = s.IntegerChoiceField(choices=BackupDefine.TYPE, default=BackupDefine.DATASET)
    node = s.SlugRelatedField(slug_field='hostname', queryset=Node.objects)  # queryset set below
    zpool = s.CharField(max_length=64)  # validated below
    desc = s.SafeCharField(max_length=128, required=False)
    bwlimit = s.IntegerField(required=False, min_value=0, max_value=2147483647)
    active = s.BooleanField(default=True)
    schedule = s.CronField()
    retention = s.IntegerField()  # limits set below
    compression = s.IntegerChoiceField(choices=BackupDefine.COMPRESSION)
    fsfreeze = s.BooleanField(default=False)

    def __init__(self, request, instance, *args, **kwargs):
        vm_template = kwargs.pop('vm_template', False)
        self._update_fields_ = list(self._update_fields_)
        super(BackupDefineSerializer, self).__init__(request, instance, *args, **kwargs)

        if not kwargs.get('many', False):
            dc_settings = request.dc.settings
            backup_nodes = get_nodes(request, is_backup=True)
            self.fields['node'].queryset = backup_nodes
            self.fields['zpool'].default = dc_settings.VMS_STORAGE_DEFAULT
            self.fields['compression'].default = dc_settings.VMS_VM_BACKUP_COMPRESSION_DEFAULT

            # Set first backup node and backup node storage available in DC
            # (used only when called by VmDefineBackup.create_from_template())
            if vm_template:
                try:
                    self.fields['node'].default = first_node = backup_nodes[0]
                except IndexError:
                    pass
                else:
                    first_node_zpools = get_zpools(request).filter(node=first_node).values_list('zpool', flat=True)

                    if first_node_zpools and dc_settings.VMS_STORAGE_DEFAULT not in first_node_zpools:
                        self.fields['zpool'].default = first_node_zpools[0]

            if request.method != 'POST':
                self.fields['type'].read_only = True

            # Limit maximum number of backups - Issue #chili-447
            if dc_settings.VMS_VM_BACKUP_LIMIT is None:
                min_count, max_count = RETENTION_MIN, RETENTION_MAX
            else:
                min_count, max_count = 1, int(dc_settings.VMS_VM_BACKUP_LIMIT)
            self.fields['retention'].validators.append(validators.MinValueValidator(min_count))
            self.fields['retention'].validators.append(validators.MaxValueValidator(max_count))

            if instance.vm.is_kvm():
                self._update_fields_.append('fsfreeze')

    def validate(self, attrs):
        try:
            zpool = attrs['zpool']
        except KeyError:
            zpool = self.object.zpool

        try:
            node = attrs['node']
        except KeyError:
            node = self.object.node

        try:
            attrs['zpool'] = get_zpools(self.request).get(node=node, zpool=zpool)
        except NodeStorage.DoesNotExist:
            self._errors['zpool'] = s.ErrorList([_('Zpool does not exist on node.')])

        # Check total number of existing backup definitions - Issue #chili-447
        if self.request.method == 'POST':
            limit = self.request.dc.settings.VMS_VM_BACKUP_DEFINE_LIMIT

            if limit is not None:
                total = self._model_.objects.filter(vm=self.object.vm).count()
                if int(limit) <= total:
                    raise s.ValidationError(_('Maximum number of backup definitions reached.'))

        return attrs


class ExtendedBackupDefineSerializer(BackupDefineSerializer):
    """Add backup count to BackupDefineSerializer"""
    backups = s.IntegerField(read_only=True)


class BackupSerializer(_HideNodeSerializer):
    """
    vms.models.Backup
    """
    _model_ = Backup
    _update_fields_ = ('note',)
    _default_fields_ = ('hostname', 'vm', 'dc', 'name', 'disk_id')

    hostname = s.CharField(source='vm_hostname', read_only=True)
    vm = s.CharField(source='vm', required=False, read_only=True)
    dc = s.CharField(source='dc', read_only=True)
    define = s.CharField(source='define.name', read_only=True)
    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=24, min_length=1)
    disk_id = s.IntegerField(source='array_disk_id', max_value=DISK_ID_MAX, min_value=DISK_ID_MIN)
    type = s.IntegerChoiceField(choices=Backup.TYPE, read_only=True)
    node = s.CharField(source='node.hostname', read_only=True)
    zpool = s.CharField(source='zpool.zpool', read_only=True)
    created = s.DateTimeField(read_only=True, required=False)
    status = s.IntegerChoiceField(choices=Backup.STATUS, read_only=True, required=False)
    size = s.IntegerField(read_only=True)
    time = s.IntegerField(read_only=True)
    file_path = s.CharField(read_only=True)
    note = s.SafeCharField(max_length=128, required=False)

    def __init__(self, request, instance, node_view=False, *args, **kwargs):
        super(BackupSerializer, self).__init__(request, instance, *args, **kwargs)
        if not node_view:
            del self.fields['dc']
