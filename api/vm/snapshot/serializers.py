from random import randint

from django.utils.translation import ugettext_lazy as _
from django.core import validators

from vms.models import SnapshotDefine, Snapshot
from api import serializers as s
from api.vm.define.vm_define_disk import DISK_ID_MIN, DISK_ID_MAX

DISK_ID_MIN += 1
DISK_ID_MAX += 1
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

            if instance.vm.is_kvm():
                self._update_fields_ = list(self._update_fields_)
                self._update_fields_.append('fsfreeze')

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
    disk_id = s.IntegerField(source='array_disk_id', max_value=DISK_ID_MAX, min_value=DISK_ID_MIN)
    note = s.SafeCharField(max_length=128, required=False)
    type = s.IntegerChoiceField(choices=Snapshot.TYPE, default=2, read_only=True)
    created = s.DateTimeField(read_only=True, required=False)
    status = s.IntegerChoiceField(choices=Snapshot.STATUS, read_only=True, required=False)
    size = s.IntegerField(read_only=True)
