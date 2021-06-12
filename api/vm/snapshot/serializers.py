from random import randint

from django.utils.translation import ugettext_lazy as _
from django.core import validators

from vms.models import SnapshotDefine, Snapshot
from api import serializers as s
from api.exceptions import ObjectNotFound, InvalidInput
from api.vm.utils import get_vm
from api.vm.define.vm_define_disk import DISK_ID_MIN, DISK_ID_MAX, DISK_ID_MAX_BHYVE
from api.vm.snapshot.utils import get_disk_id

DISK_ID_MIN += 1
DISK_ID_MAX += 1
DISK_ID_MAX_BHYVE += 1
RETENTION_MIN = 0
RETENTION_MAX = 65536


class _HideNodeSerializer(s.InstanceSerializer):
    """Replace node with node color"""

    @property
    def data(self):
        if self._data is None:
            data = super(_HideNodeSerializer, self).data

            if self.many:
                data_list = data
                obj_list = self.object
            else:
                data_list = [data]
                obj_list = [self.object]

            for i, obj in enumerate(data_list):
                # Display node color instead of name
                if 'node' in obj and obj['node'] and obj_list[i].node:
                    if not self.request.user.is_admin(self.request):
                        obj['node'] = obj_list[i].node.color

            self._data = data

        return self._data


def define_schedule_defaults(defname):
    """Some useful default schedules according to define name"""
    ret = {}

    if defname == 'daily':
        ret['schedule'] = '%s %s * * *' % (randint(0, 59), randint(0, 23))
        ret['retention'] = 30
    elif defname == 'hourly':
        ret['schedule'] = '%s * * * *' % (randint(0, 59),)
        ret['retention'] = 24
    elif defname == 'weekly':
        ret['schedule'] = '%s %s * * %s' % (randint(0, 59), randint(0, 23), randint(0, 6))
        ret['retention'] = 12
    elif defname == 'monthly':
        ret['schedule'] = '%s %s %s * *' % (randint(0, 59), randint(0, 23), randint(1, 28))
        ret['retention'] = 6

    return ret


class SnapshotDefineSerializer(s.InstanceSerializer):
    """
    vms.models.SnapshotDefine
    """
    _model_ = SnapshotDefine
    _update_fields_ = ('desc', 'active', 'schedule', 'retention')
    _default_fields_ = ('hostname', 'name', 'disk_id')

    hostname = s.CharField(source='vm.hostname', read_only=True)
    vm_uuid = s.CharField(source='vm.uuid', read_only=True)
    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=8, min_length=1)
    disk_id = s.IntegerField(source='array_disk_id', max_value=DISK_ID_MAX, min_value=DISK_ID_MIN)
    desc = s.SafeCharField(max_length=128, required=False)
    active = s.BooleanField(default=True)
    schedule = s.CronField()
    retention = s.IntegerField()  # limits set below
    fsfreeze = s.BooleanField(default=False)

    def __init__(self, request, instance, *args, **kwargs):
        super(SnapshotDefineSerializer, self).__init__(request, instance, *args, **kwargs)

        if not kwargs.get('many', False):
            dc_settings = request.dc.settings

            # Limit maximum number of snapshots - Issue #chili-447
            if dc_settings.VMS_VM_SNAPSHOT_LIMIT_AUTO is None:
                min_count, max_count = RETENTION_MIN, RETENTION_MAX
            else:
                min_count, max_count = 1, int(dc_settings.VMS_VM_SNAPSHOT_LIMIT_AUTO)

            self.fields['retention'].validators.append(validators.MinValueValidator(min_count))
            self.fields['retention'].validators.append(validators.MaxValueValidator(max_count))

            if instance.vm.is_hvm():
                self._update_fields_ = list(self._update_fields_)
                self._update_fields_.append('fsfreeze')
                if instance.vm.is_bhyve():
                    self.fields['disk_id'].max_value = DISK_ID_MAX_BHYVE

    def validate(self, attrs):
        # Check total number of existing snapshot definitions - Issue #chili-447
        if self.request.method == 'POST':
            limit = self.request.dc.settings.VMS_VM_SNAPSHOT_DEFINE_LIMIT

            if limit is not None:
                total = self._model_.objects.filter(vm=self.object.vm).count()
                if int(limit) <= total:
                    raise s.ValidationError(_('Maximum number of snapshot definitions reached.'))

        return attrs


class ExtendedSnapshotDefineSerializer(SnapshotDefineSerializer):
    """Add snapshot count to SnapshotDefineSerializer"""
    snapshots = s.IntegerField(read_only=True)


class SnapshotSerializer(s.InstanceSerializer):
    """
    vms.models.Snapshot
    """
    _model_ = Snapshot
    _update_fields_ = ('note',)
    _default_fields_ = ('hostname', 'name', 'disk_id')

    hostname = s.CharField(source='vm.hostname', read_only=True)
    vm_uuid = s.CharField(source='vm.uuid', read_only=True)
    define = s.CharField(source='define.name', read_only=True)
    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=24, min_length=1)
    # we're using DISK_ID_MAX_BHYVE because it's bigger
    disk_id = s.IntegerField(source='array_disk_id', max_value=DISK_ID_MAX_BHYVE, min_value=DISK_ID_MIN)
    note = s.SafeCharField(max_length=128, required=False)
    type = s.IntegerChoiceField(choices=Snapshot.TYPE, default=2, read_only=True)
    created = s.DateTimeField(read_only=True, required=False)
    status = s.IntegerChoiceField(choices=Snapshot.STATUS, read_only=True, required=False)
    size = s.IntegerField(read_only=True)
    id = s.SafeCharField(read_only=True)


class SnapshotRestoreSerializer(s.Serializer):
    target_hostname_or_uuid = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', required=False)
    # we're using DISK_ID_MAX_BHYVE because it's bigger
    target_disk_id = s.IntegerField(max_value=DISK_ID_MAX_BHYVE, min_value=DISK_ID_MIN, required=False)
    force = s.BooleanField(default=True)

    def __init__(self, request, vm, *args, **kwargs):
        self.request = request
        self.vm = vm
        self.target_vm = vm
        self.target_vm_disk_id = None
        self.target_vm_real_disk_id = None
        self.target_vm_disk_zfs_filesystem = None
        super(SnapshotRestoreSerializer, self).__init__(*args, **kwargs)

    def validate(self, attrs):
        target_hostname_or_uuid = attrs.get('target_hostname_or_uuid', None)
        target_disk_id = attrs.get('target_disk_id', None)

        if target_hostname_or_uuid and not target_disk_id:
            err_msg = _('This field is required when target_hostname_or_uuid is specified.')
            self._errors['target_disk_id'] = s.ErrorList([err_msg])
            return attrs
        elif not target_hostname_or_uuid and target_disk_id:
            err_msg = _('This field is required when target_disk_id is specified.')
            self._errors['target_hostname_or_uuid'] = s.ErrorList([err_msg])
            return attrs
        elif target_hostname_or_uuid and target_disk_id:
            try:
                self.target_vm = get_vm(self.request, target_hostname_or_uuid, exists_ok=True, noexists_fail=True,
                                        check_node_status=None)
            except ObjectNotFound as exc:
                self._errors['target_hostname_or_uuid'] = s.ErrorList([exc.detail])
            else:
                try:
                    self.target_vm_disk_id, self.target_vm_real_disk_id, self.target_vm_disk_zfs_filesystem = \
                        get_disk_id(self.request, self.target_vm, disk_id=target_disk_id)
                except InvalidInput as exc:
                    self._errors['target_disk_id'] = s.ErrorList([exc.detail])

        return attrs
