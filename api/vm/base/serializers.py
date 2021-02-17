from frozendict import frozendict

from api import serializers as s
from vms.models import Vm, Node


class VmCreateSerializer(s.Serializer):
    recreate = s.BooleanField(default=False)
    force = s.BooleanField(default=False)


class VmBaseSerializer(s.Serializer):
    """Save request and display node color for non-admin users"""
    def __init__(self, request, *args, **kwargs):
        self.request = request
        super(VmBaseSerializer, self).__init__(*args, **kwargs)

    @property
    def data(self):
        if self._data is None:
            data = super(VmBaseSerializer, self).data

            if self.many:
                data_list = data
                obj_list = self.object
            else:
                data_list = [data]
                obj_list = [self.object]

            for i, vm in enumerate(data_list):
                # Display node color instead of name
                if 'node' in vm and vm['node'] and obj_list[i].node:
                    if not self.request.user.is_admin(self.request):
                        vm['node'] = obj_list[i].node.color

                # Add changed attribute
                vm['changed'] = obj_list[i].json_changed()

            self._data = data

        return self._data


class VmSerializer(VmBaseSerializer):
    """
    VM details (read-only)
    """
    hostname = s.Field()
    uuid = s.CharField(read_only=True)
    alias = s.Field()
    node = s.SlugRelatedField(slug_field='hostname', read_only=True, required=False)
    owner = s.SlugRelatedField(slug_field='username', read_only=True)
    status = s.DisplayChoiceField(choices=Vm.STATUS, read_only=True)
    node_status = s.DisplayChoiceField(source='node.status', choices=Node.STATUS_DB, read_only=True)
    vcpus = s.IntegerField(read_only=True)
    ram = s.IntegerField(read_only=True)
    disk = s.IntegerField(read_only=True)
    ips = s.ArrayField(read_only=True)
    uptime = s.IntegerField(source='uptime_actual', read_only=True)
    locked = s.BooleanField(read_only=True)


class ExtendedVmSerializer(VmSerializer):
    """
    Extended VM details (read-only)
    """
    extra_select = frozendict({
        'snapshots': '''SELECT COUNT(*) FROM "vms_snapshot" WHERE "vms_vm"."uuid" = "vms_snapshot"."vm_id"''',

        'backups': '''SELECT COUNT(*) FROM "vms_backup" WHERE "vms_vm"."uuid" = "vms_backup"."vm_id"''',

        'snapshot_define_active': '''SELECT COUNT(*) FROM "vms_snapshotdefine"
    LEFT OUTER JOIN "django_celery_beat_periodictask" ON ("vms_snapshotdefine"."periodic_task_id" = "django_celery_beat_periodictask"."id")
    WHERE "vms_snapshotdefine"."vm_id" = "vms_vm"."uuid" AND "django_celery_beat_periodictask"."enabled" = True''',

        'snapshot_define_inactive': '''SELECT COUNT(*) FROM "vms_snapshotdefine"
    LEFT OUTER JOIN "django_celery_beat_periodictask" ON ("vms_snapshotdefine"."periodic_task_id" = "django_celery_beat_periodictask"."id")
    WHERE "vms_snapshotdefine"."vm_id" = "vms_vm"."uuid" AND "django_celery_beat_periodictask"."enabled" = False''',

        'backup_define_active': '''SELECT COUNT(*) FROM "vms_backupdefine"
    LEFT OUTER JOIN "django_celery_beat_periodictask" ON ("vms_backupdefine"."periodic_task_id" = "django_celery_beat_periodictask"."id")
    WHERE "vms_backupdefine"."vm_id" = "vms_vm"."uuid" AND "django_celery_beat_periodictask"."enabled" = True''',

        'backup_define_inactive': '''SELECT COUNT(*) FROM "vms_backupdefine"
    LEFT OUTER JOIN "django_celery_beat_periodictask" ON ("vms_backupdefine"."periodic_task_id" = "django_celery_beat_periodictask"."id")
    WHERE "vms_backupdefine"."vm_id" = "vms_vm"."uuid" AND "django_celery_beat_periodictask"."enabled" = False''',

        'slaves': '''SELECT COUNT(*) FROM "vms_slavevm" WHERE "vms_vm"."uuid" = "vms_slavevm"."master_vm_id"''',
    })

    tags = s.TagField(required=False, default=[])
    snapshot_define_inactive = s.IntegerField(read_only=True)
    snapshot_define_active = s.IntegerField(read_only=True)
    snapshots = s.IntegerField(read_only=True)
    backup_define_inactive = s.IntegerField(read_only=True)
    backup_define_active = s.IntegerField(read_only=True)
    backups = s.IntegerField(read_only=True)
    slaves = s.IntegerField(read_only=True)
    size_snapshots = s.IntegerField(read_only=True)
    size_backups = s.IntegerField(read_only=True)
