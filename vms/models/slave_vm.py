from django.db import models, transaction
from django.utils.translation import ugettext_noop, ugettext_lazy as _

# noinspection PyProtectedMember
from vms.models.base import _JsonPickleModel
from vms.models.vm import Vm


class SlaveVm(_JsonPickleModel):
    """
    Vm model extension for saving migration and replication stuff.
    The slave VM must be stored in the Vm table to populate resources in a DC.
    """
    REPLICA_PREFIX = '_replica-'
    MIGRATION_PREFIX = '__migrate-'

    DIS = 0
    OFF = 1
    ON = 2

    SYNC_STATUS = (
        (DIS, ugettext_noop('disabled')),
        (OFF, ugettext_noop('paused')),
        (ON, ugettext_noop('enabled')),
    )

    vm = models.OneToOneField(Vm, on_delete=models.CASCADE)
    master_vm = models.ForeignKey(Vm, related_name='slave_vm', verbose_name=_('Master server'),
                                  on_delete=models.CASCADE)
    name = models.CharField(_('Slave name'), max_length=24, blank=True, default='', db_index=True)
    sync_status = models.SmallIntegerField(_('Replication status'), choices=SYNC_STATUS, default=DIS)
    last_sync = models.DateTimeField(_('Last synced'), null=True, blank=True, default=None)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Slave VM')
        verbose_name_plural = _('Slave VM')

    # noinspection PyUnusedLocal
    def __init__(self, *args, **kwargs):
        master_vm = kwargs.pop('_master_vm', None)

        if master_vm:  # Master VM
            # Create new slave VM
            slave_vm = Vm()  # Set new flag and generate new uuid

            # Copy all field values from master to slave
            # noinspection PyProtectedMember
            for field in master_vm._meta.fields:
                attname = field.attname
                if attname not in ('uuid', 'hostname', 'enc_json_active', 'vnc_port', 'created', 'changed'):
                    setattr(slave_vm, attname, getattr(master_vm, attname))

            # Replace master uuid in json with slave uuid
            self.json = slave_vm.json.load(slave_vm.json.dump().replace(master_vm.uuid, slave_vm.uuid))

            super(SlaveVm, self).__init__(*args, **kwargs)
            self.master_vm = master_vm
            self.vm = slave_vm
            self.vm.status = Vm.NOTCREATED  # otherwise vm.delete() wouldn't work
        else:
            super(SlaveVm, self).__init__(*args, **kwargs)

    def __unicode__(self):
        return '%s' % self.vm

    def save(self, **kwargs):
        """Save and update master_vm.slave_vms if creating new slave VM"""
        if self.vm.new:
            with transaction.atomic():
                self.vm.save(**kwargs)
                self.master_vm.add_slave_vm(self.vm)
                self.master_vm.save(update_fields=('slave_vms', 'changed'))
                ret = super(SlaveVm, self).save()
                self.vm.lock()
                return ret
        else:
            return super(SlaveVm, self).save(**kwargs)

    # noinspection PyUnusedLocal
    @staticmethod
    def post_delete(sender, instance, **kwargs):
        """Update master_vm.slave_vms and delete the slave VM"""
        with transaction.atomic():
            instance.master_vm.delete_slave_vm(instance.vm)
            instance.vm.delete()
            instance.master_vm.save(update_fields=('slave_vms', 'changed'))

    @classmethod
    def get_by_uuid(cls, uuid, sr=('master_vm', 'vm', 'vm__node')):
        return cls.objects.select_related(*sr).get(vm=uuid)

    @property
    def uuid(self):
        return self.vm.uuid

    @property
    def hostname(self):
        return self.vm.hostname

    @hostname.setter
    def hostname(self, value):
        self.vm.hostname = value

    @property
    def node(self):
        return self.vm.node

    @node.setter
    def node(self, value):
        """Set node silently"""
        self.vm.node = self.vm._orig_node = value

    @property
    def reserve_resources(self):
        """Whether to reserve resources (CPU, RAM) for the related VM object"""
        return self.json.get('reserve_resources', True)

    @reserve_resources.setter
    def reserve_resources(self, value):
        """Whether to reserve resources (CPU, RAM) for the related VM object"""
        self.save_item('reserve_resources', bool(value), save=False)

    @property
    def rep_id(self):
        """Replication ID"""
        return self.json.get('rep_id', None)

    @rep_id.setter
    def rep_id(self, value):
        """Replication ID"""
        self.save_item('rep_id', int(value), save=False)

    @property
    def rep_sleep_time(self):
        """Replication sleep time"""
        return self.json.get('rep_sleep_time', None)

    @rep_sleep_time.setter
    def rep_sleep_time(self, value):
        """Replication sleep time"""
        self.save_item('rep_sleep_time', int(value), save=False)

    @property
    def rep_bwlimit(self):
        """Replication bandwidth limit"""
        return self.json.get('rep_bwlimit', None)

    @rep_bwlimit.setter
    def rep_bwlimit(self, value):
        """Replication bandwidth limit"""
        if value is not None:
            value = int(value)
        self.save_item('rep_bwlimit', value, save=False)

    @property
    def rep_enabled(self):
        """Wrapper around sync_status"""
        return self.sync_status == self.ON

    @rep_enabled.setter
    def rep_enabled(self, value):
        """Wrapper around sync_status"""
        if value:
            self.sync_status = self.ON
        else:
            self.sync_status = self.OFF

    @property
    def rep_reinit_required(self):
        """True if reinit is required"""
        return self.json.get('rep_reinit_required', False)

    @rep_reinit_required.setter
    def rep_reinit_required(self, value):
        """Set after successful failover"""
        self.save_item('rep_reinit_required', value, save=False)

    @classmethod
    def get_rep_hostname(cls, hostname, rep_id):
        """Compose slave VM hostname from replication identifier"""
        return '%s%s-%s' % (cls.REPLICA_PREFIX, rep_id, hostname)

    def set_rep_hostname(self):
        """Set replication hostname"""
        assert self.rep_id is not None
        self.hostname = self.get_rep_hostname(self.master_vm.hostname, self.rep_id)

    @classmethod
    def get_migration_hostname(cls, hostname):
        """Create ghost VM hostname"""
        return '%s%s' % (cls.MIGRATION_PREFIX, hostname)

    def set_migration_hostname(self):
        """Set ghost VM hostname"""
        self.hostname = self.get_migration_hostname(self.master_vm.hostname)

    def is_used_for_migration(self):
        """Is this slave VM used for migration purposes?"""
        return self.hostname.startswith(self.MIGRATION_PREFIX)

    @staticmethod
    def get_zpool(disk):
        """Return zpool part from zfs_filesystem attribute"""
        try:
            return disk['zfs_filesystem'].split('/')[0]
        except (KeyError, IndexError):
            raise ValueError('Invalid disk configuration.')

    @property
    def root_zpool(self):
        """Changed root zpool; used by replication"""
        zpool = self.get_zpool(self.vm.json)
        if zpool != self.get_zpool(self.master_vm.json):
            return zpool

    @property
    def disk_zpools(self):
        """Changed disk zpools; used by replication"""
        if self.vm.is_kvm():
            disks = self.vm.json_get_disks()
            master_disks = self.master_vm.json_get_disks()
            return {i + 1: disk['zpool'] for i, disk in enumerate(disks) if disk['zpool'] != master_disks[i]['zpool']}
        else:
            return {}

    @property
    def web_data(self):
        """Return dict used in server details web template"""
        return {
            'repname': self.name,
            'node': self.node.hostname,
            'reserve_resources': self.reserve_resources,
            'sleep_time': self.rep_sleep_time,
            'enabled': self.rep_enabled,
            'reinit_required': self.rep_reinit_required,
            'last_sync': self.last_sync,
            'hostname': self.master_vm.hostname,
        }

    def fail_over(self):
        """Fail over to slave VM. Change old master VM to slave VM"""
        from vms.models import TaskLogEntry

        new_vm, old_vm = self.vm, self.master_vm  # Save VM objects
        new_vm.info = old_vm.info  # Sync zabbix, node_history and other stuff
        new_vm.update_node_history(orig_node=old_vm.node)  # Preserve node history (simulate node change)
        # Exchanged uptime and datetime information
        new_vm.uptime, old_vm.uptime = old_vm.uptime, new_vm.uptime
        new_vm.uptime_changed, old_vm.uptime_changed = old_vm.uptime_changed, new_vm.uptime_changed
        new_vm.created, old_vm.created = old_vm.created, new_vm.created
        new_vm.hostname, old_vm.hostname = old_vm.hostname, new_vm.hostname  # Switch hostname
        # The VM switch
        old_vm.delete_slave_vm(new_vm)
        new_vm.add_slave_vm(old_vm)
        self.master_vm = new_vm
        self.vm = old_vm
        self.rep_reinit_required = True

        with transaction.atomic():
            # Hostname is unique so temporary rename old_vm to something non-existent
            old_vm_hostname = old_vm.hostname
            old_vm.hostname = '_' + old_vm_hostname
            old_vm.save()
            new_vm.save()
            old_vm.hostname = old_vm_hostname
            old_vm.save(update_fields=('hostname',))
            self.save()

            # Update relations
            # noinspection PyProtectedMember
            for rel in old_vm._meta.get_all_related_objects():
                if rel.name in ('slavevm', 'slave_vm'):
                    continue
                rel_set = getattr(old_vm, rel.get_accessor_name())
                rel_set.update(**{rel.field.name: new_vm})

            # Update task log entries
            TaskLogEntry.objects.filter(object_pk=old_vm.pk).update(object_pk=new_vm.pk)

        # Recalculate node resources after failover
        if not self.reserve_resources:
            old_vm.save(update_node_resources=True)
            new_vm.save(update_node_resources=True)

        return new_vm

    @staticmethod
    def switch_vm_snapshots_node_storages(vm, nss=()):
        """Change zpool attribute for every VM snapshot to current node_storage"""
        vm_disk_ns_map = vm.get_node_storages_disk_map()
        res = {}

        for real_disk_id, ns in vm_disk_ns_map.items():
            res[real_disk_id] = vm.snapshot_set.filter(disk_id=real_disk_id).update(zpool=ns)

        if res:  # Update node storage snapshot size counters
            nss = set(nss)
            nss.update(vm_disk_ns_map.values())

            for ns in nss:
                ns.save(update_resources=True, update_dcnode_resources=True, recalculate_vms_size=False,
                        recalculate_snapshots_size=True, recalculate_images_size=False, recalculate_backups_size=False,
                        recalculate_dc_snapshots_size=(vm.dc,))

        return res
