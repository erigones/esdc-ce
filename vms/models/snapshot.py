from datetime import datetime
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

# noinspection PyProtectedMember
from vms.models.base import _StatusModel, _VmDiskModel, _ScheduleModel
from vms.models.vm import Vm
from vms.models.storage import get_cached_size, clear_cached_size, NodeStorage
from que import TT_AUTO, TT_EXEC


class SnapshotDefine(_VmDiskModel, _ScheduleModel):
    """
    Virtual Machine automatic snapshot definition.
    """
    # id (implicit), Inherited: disk_id, schedule (property), active (property)
    vm = models.ForeignKey(Vm, verbose_name=_('Server'))
    name = models.CharField(_('Name'), max_length=16)  # User ID
    desc = models.CharField(_('Description'), max_length=128, blank=True)
    retention = models.IntegerField(_('Retention'))  # max count
    fsfreeze = models.BooleanField(_('Application-Consistent?'), default=False)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Snapshot definition')
        verbose_name_plural = _('Snapshot definitions')
        unique_together = (('vm', 'disk_id', 'name'),)

    def __unicode__(self):
        return '%s-disk%s %s/%s' % (self.vm_id, self.disk_id, self.name, self.retention)

    @property
    def web_data(self):
        """Return dict used in html templates"""
        return {
            'name': self.name,
            'disk_id': self.array_disk_id,
            'schedule': self.schedule,
            'retention': self.retention,
            'active': self.active,
            'fsfreeze': self.fsfreeze,
            'desc': self.desc,
        }

    def _new_periodic_task(self):
        """Return new instance of PeriodicTask"""
        return self.PT(name='snapshot-%s-%s-disk%s' % (self.name, self.vm_id, self.disk_id),
                       task='api.vm.snapshot.tasks.vm_snapshot_beat', args='[%d]' % self.id,
                       queue='mgmt', expires=None)  # expires bug: https://github.com/celery/django-celery/pull/271

    def generate_snapshot_name(self):
        """Create name for new snapshot"""
        return '%s-%s' % (self.name, timezone.now().strftime('%Y%m%d_%H%M%S'))


class Snapshot(_StatusModel, _VmDiskModel):
    """
    Virtual Machine snapshots.
    """
    SNAPSHOT_SIZE_TOTAL_KEY = 'snapshot-size-total:%s'  # %s = zpool.id (NodeStorage)
    REP_SNAPSHOT_SIZE_TOTAL_KEY = 'rep-snapshot-size-total:%s'  # %s = zpool.id (NodeStorage)
    SNAPSHOT_SIZE_DC_KEY = 'snapshot-size-dc:%s:%s'  # %s = dc.id:zpool.id (NodeStorage)
    SNAPSHOT_SIZE_TOTAL_DC_KEY = 'snapshot-size-total-dc:%s'  # %s = dc.id
    SNAPSHOT_SIZE_TOTAL_VM_KEY = 'snapshot-size-total-vm:%s'  # %s = vm.uuid
    USER_PREFIX = ('es-', 'as-')

    AUTO = 1
    MANUAL = 2
    TYPE = (
        (AUTO, _('Automatic')),
        (MANUAL, _('Manual')),
    )

    OK = 1
    PENDING = 2
    ROLLBACK = 3
    LOST = 4
    STATUS = (
        (OK, _('ok')),
        (PENDING, _('pending')),
        (ROLLBACK, _('rollback')),
        (LOST, _('lost')),
    )
    LOCKED = frozenset([PENDING, ROLLBACK])

    _cache_status = False  # _StatusModel

    # id (implicit), Inherited: status_change, created, changed, disk_id
    vm = models.ForeignKey(Vm, verbose_name=_('Server'))
    define = models.ForeignKey(SnapshotDefine, verbose_name=_('Snapshot definition'), null=True, blank=True,
                               on_delete=models.SET_NULL)
    name = models.CharField(_('Name'), max_length=32)
    type = models.SmallIntegerField(_('Type'), choices=TYPE, default=MANUAL)
    status = models.SmallIntegerField(_('Status'), choices=STATUS)
    zpool = models.ForeignKey(NodeStorage, verbose_name=_('Zpool'))
    size = models.BigIntegerField(_('Size'), null=True, blank=True)  # bytes
    note = models.CharField(_('Note'), max_length=255, blank=True)
    fsfreeze = models.BooleanField(_('Application-Consistent?'), default=False)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Snapshot')
        verbose_name_plural = _('Snapshots')
        unique_together = (('vm', 'disk_id', 'name'),)

    def __unicode__(self):
        return '%s-disk%s@%s' % (self.vm_id, self.disk_id, self.name)

    @property  # Gui helper
    def snapid(self):
        return '%s_%s' % (self.array_disk_id, self.name)

    @property  # Api helper
    def zfs_name(self):
        if self.type == self.AUTO:
            t = TT_AUTO
        else:
            t = TT_EXEC
        return '%ss-%s' % (t, self.id)

    @property
    def locked(self):
        return self.status in self.LOCKED

    # noinspection PyShadowingBuiltins
    @classmethod
    def create_from_zfs_name(cls, zfs_name, status=OK, name=None, timestamp=None, **kwargs):
        """Create new snapshot from info gathered from compute node"""
        t, id = zfs_name.split('-', 1)
        t = t[0]

        if t == TT_EXEC:
            type = cls.MANUAL
        elif t == TT_AUTO:
            type = cls.AUTO
        else:
            raise AssertionError('Unknown snapshot type')

        if not name or name == '-':
            name = zfs_name

        snap = cls(id=int(id), name=name, type=type, status=status, **kwargs)

        if timestamp:
            snap.created = datetime.fromtimestamp(timestamp, timezone.utc)

        snap.save(force_insert=True)

        return snap

    @classmethod
    def get_total_dc_size(cls, dc):
        """Return cumulative snapshot size for one DC"""
        key = cls.SNAPSHOT_SIZE_TOTAL_DC_KEY % dc.id
        qs = cls.objects.filter(vm__dc=dc).exclude(status__in=(cls.PENDING, cls.LOST), size__isnull=True)

        return get_cached_size(key, qs)

    @classmethod
    def get_total_vm_size(cls, vm):
        """Return cumulative snapshot size for one vM"""
        key = cls.SNAPSHOT_SIZE_TOTAL_VM_KEY % vm.uuid
        qs = cls.objects.filter(vm=vm).exclude(status__in=(cls.PENDING, cls.LOST), size__isnull=True)

        return get_cached_size(key, qs)

    @classmethod
    def clear_total_dc_size(cls, dc):
        return clear_cached_size(cls.SNAPSHOT_SIZE_TOTAL_DC_KEY % getattr(dc, 'id', dc))

    @classmethod
    def clear_total_vm_size(cls, vm):
        return clear_cached_size(cls.SNAPSHOT_SIZE_TOTAL_VM_KEY % getattr(vm, 'uuid', vm))

    @classmethod
    def update_resources(cls, ns, vm, dc=None):
        """Update NodeStorage and Storage size_free"""
        dc = dc or vm.dc
        ns.save(update_resources=True, update_dcnode_resources=True, recalculate_vms_size=False,
                recalculate_snapshots_size=True, recalculate_images_size=False, recalculate_backups_size=False,
                recalculate_dc_snapshots_size=(dc,))
        cls.clear_total_dc_size(dc)

        if vm:
            cls.clear_total_vm_size(vm)
