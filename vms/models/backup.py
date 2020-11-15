from os import path

from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from frozendict import frozendict

# noinspection PyProtectedMember
from vms.models.base import _JsonPickleModel, _StatusModel, _VmDiskModel, _ScheduleModel
from vms.models.dc import Dc
from vms.models.vm import Vm
from vms.models.node import Node
from vms.models.storage import get_cached_size, clear_cached_size, NodeStorage


class BackupDefine(_VmDiskModel, _ScheduleModel):
    """
    Virtual Machine backup definition and schedule.
    """
    DATASET = 1
    FILE = 2
    TYPE = (
        (DATASET, _('Dataset')),
        (FILE, _('File')),
    )

    NONE = 0
    GZIP = 1
    BZIP2 = 2
    XZ = 3
    COMPRESSION = (
        (NONE, _('None')),
        (GZIP, 'gzip'),
        (BZIP2, 'bzip2'),
        (XZ, 'xz'),
    )

    FILE_SUFFIX = frozendict({
        NONE: 'zfs',
        GZIP: 'zfs.gz',
        BZIP2: 'zfs.bz2',
        XZ: 'zfs.xz',
    })

    # id (implicit), Inherited: disk_id, schedule (property), active (property)
    vm = models.ForeignKey(Vm, verbose_name=_('Server'))
    name = models.CharField(_('Name'), max_length=16)  # User ID
    node = models.ForeignKey(Node, verbose_name=_('Node'))  # Where?
    zpool = models.ForeignKey(NodeStorage, verbose_name=_('Zpool'))  # Where?
    type = models.SmallIntegerField(_('Type'), choices=TYPE, default=DATASET)
    desc = models.CharField(_('Description'), max_length=128, blank=True)
    bwlimit = models.IntegerField(_('Bandwidth limit'), blank=True, null=True)  # bytes
    retention = models.IntegerField(_('Retention'))  # max count
    compression = models.SmallIntegerField(_('Compression'), choices=COMPRESSION, default=NONE)
    fsfreeze = models.BooleanField(_('Application-Consistent?'), default=False)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Backup definition')
        verbose_name_plural = _('Backup definitions')
        unique_together = (('vm', 'disk_id', 'name'),)

    def __unicode__(self):
        return '%s-disk%s %s/%s' % (self.vm_id, self.disk_id, self.name, self.retention)

    @property
    def web_data(self):
        """Return dict used in html templates"""
        return {
            'name': self.name,
            'disk_id': self.array_disk_id,
            'node': self.node.hostname,
            'zpool': self.zpool.zpool,
            'type': self.type,
            'bwlimit': self.bwlimit,
            'compression': self.compression,
            'schedule': self.schedule,
            'retention': self.retention,
            'active': self.active,
            'fsfreeze': self.fsfreeze,
            'desc': self.desc,
        }

    def _new_periodic_task(self):
        """Return new instance of PeriodicTask"""
        return self.PT(name='backup-%s-%s-disk%s' % (self.name, self.vm_id, self.disk_id),
                       task='api.vm.backup.tasks.vm_backup_beat', args='[%d]' % self.id,
                       queue='mgmt', expires=None)  # expires bug: https://github.com/celery/django-celery/pull/271

    def generate_backup_name(self):
        """Create name for new backup"""
        return '%s-%s' % (self.name, timezone.now().strftime('%Y%m%d_%H%M%S'))


class Backup(_VmDiskModel, _StatusModel, _JsonPickleModel):
    """
    List of backups.
    """
    _cache_status = False  # _StatusModel
    _disk_size = None  # Disk size cache
    _disks = None  # Disk list cache
    # Used in NodeStorage.size_backups
    BACKUP_SIZE_TOTAL_KEY = 'backup-size-total:%s'  # %s = zpool.id (NodeStorage)
    BACKUP_SIZE_DC_KEY = 'backup-size-dc:%s:%s'  # %s = dc.id:zpool.id (NodeStorage)
    BACKUP_SIZE_TOTAL_DC_KEY = 'backup-size-total-dc:%s'  # %s = dc.id
    BACKUP_SIZE_TOTAL_VM_KEY = 'backup-size-total-vm:%s'  # %s = vm.uuid

    DATASET = BackupDefine.DATASET
    FILE = BackupDefine.FILE
    TYPE = BackupDefine.TYPE

    OK = 1
    PENDING = 2
    RESTORE = 3
    LOST = 4
    STATUS = (
        (OK, _('ok')),
        (PENDING, _('pending')),
        (RESTORE, _('restore')),
        (LOST, _('lost')),
    )
    LOCKED = frozenset([PENDING, RESTORE])

    # id (implicit), Inherited: status_change, created, changed, json, disk_id
    dc = models.ForeignKey(Dc, verbose_name=_('Datacenter'))
    vm = models.ForeignKey(Vm, verbose_name=_('Server'), null=True, blank=True, on_delete=models.SET_NULL)
    vm_hostname = models.CharField(_('Server hostname'), max_length=128)  # original hostname
    vm_disk_id = models.SmallIntegerField('Array disk ID')  # json disk_id
    define = models.ForeignKey(BackupDefine, verbose_name=_('Backup definition'), null=True, blank=True,
                               on_delete=models.SET_NULL)
    name = models.CharField(_('Name'), max_length=32)  # define name + timestamp
    status = models.SmallIntegerField(_('Status'), choices=STATUS)
    file_path = models.CharField(_('File path'), max_length=255, blank=True)
    manifest_path = models.CharField(_('Manifest path'), max_length=255, blank=True)
    checksum = models.CharField(_('Checksum'), max_length=40, blank=True)
    node = models.ForeignKey(Node, verbose_name=_('Node'))
    zpool = models.ForeignKey(NodeStorage, verbose_name=_('Zpool'))
    type = models.SmallIntegerField(_('Type'), choices=TYPE)
    size = models.BigIntegerField(_('Size'), null=True, blank=True)  # bytes
    time = models.IntegerField(_('Duration'), null=True, blank=True)  # seconds
    note = models.CharField(_('Note'), max_length=255, blank=True)
    last = models.BooleanField(_('Last?'), default=False)  # TODO: index?
    fsfreeze = models.BooleanField(_('Application-Consistent?'), default=False)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Backup')
        verbose_name_plural = _('Backups')
        unique_together = (('vm_hostname', 'vm_disk_id', 'name'),)
        # index_together = (('created',),)

    def __unicode__(self):
        return '%s-disk%s@%s' % (self.vm_hostname, self.disk_id, self.name)

    def get_disk_map(self):  # See _VmDiskModel
        """Return real_disk_id -> disk_id mapping"""
        return Vm.get_disk_map(self.json)

    def _get_disks(self):
        if self._disks is None:
            json = self.json
            self._disks = Vm.parse_json_disks(json['uuid'], json, json.get('brand', 'kvm') == 'kvm')
        return self._disks

    @property
    def locked(self):
        return self.status in self.LOCKED

    @property
    def array_disk_id(self):
        """Faster array_disk_id"""
        return int(self.vm_disk_id) + 1

    @property
    def vm_uuid(self):
        """VM uuid"""
        if self.vm:
            return self.vm.uuid
        return self.json['uuid']

    @property
    def vm_hostname_real(self):
        """Real VM hostname"""
        if self.vm:
            return self.vm.hostname
        return self.vm_hostname

    @property
    def vm_brand(self):
        """VM brand"""
        return self.json.get('brand', 'kvm')

    @property
    def disk_size(self):
        """Return disk size in MB"""
        if self._disk_size is None:
            self._disk_size = self._get_disks()[int(self.vm_disk_id)]['size']
        return self._disk_size

    @property
    def zfs_filesystem(self):
        """Return zfs_filesystem of VM's disk this backup is for"""
        return self._get_disks()[int(self.vm_disk_id)]['zfs_filesystem']

    @property
    def zfs_filesystem_real(self):
        """Return zfs_filesystem of VM's disk this backup is for"""
        if self.vm:
            try:
                vm_disks = self.vm.json_active_get_disks()
                disk_map = self.vm.get_disk_map(vm_disks)
                return vm_disks[disk_map[self.disk_id]]['zfs_filesystem']
            except (IndexError, KeyError):
                return self.zfs_filesystem
        else:
            return self.zfs_filesystem

    @property  # Gui helper
    def bkpid(self):
        return '%s_%s' % (self.array_disk_id, self.name)

    @property
    def snap_name(self):
        """Return snapshot name used for dataset backup"""
        return 'is-%d' % self.id

    @property
    def file_name(self):
        """Return backup file name"""
        assert self.name
        define = self.define
        return '%s-full.%s' % (self.name, define.FILE_SUFFIX[define.compression])

    def create_file_path(self):
        """Return backup file path"""
        # /zones/backups/file/<uuid>/disk0/<file_name>.zfs
        return path.join('/', self.zpool.zpool, self.dc.settings.VMS_VM_BACKUP_FILE_DIR, self.vm_uuid,
                         'disk%s' % self.disk_id, self.file_name)

    def create_dataset_path(self):
        """Return backup dataset"""
        # zones/backups/ds/<uuid>-disk0
        return path.join(self.zpool.zpool, self.dc.settings.VMS_VM_BACKUP_DS_DIR,
                         '%s-disk%s' % (self.vm_uuid, self.disk_id))

    def create_file_manifest_path(self):
        """Return backup file manifest path"""
        # /zones/backups/manifests/file/<uuid>/disk0/<file_name>.zfs.json
        return path.join('/', self.zpool.zpool, self.dc.settings.VMS_VM_BACKUP_MANIFESTS_FILE_DIR, self.vm_uuid,
                         'disk%s' % self.disk_id, '%s.json' % self.file_name)

    def create_dataset_manifest_path(self):
        """Return backup dataset manifest path"""
        # zones/backups/manifests/ds/<uuid>-disk0/<snap_name>.json
        return path.join('/', self.zpool.zpool, self.dc.settings.VMS_VM_BACKUP_MANIFESTS_DS_DIR,
                         '%s-disk%s' % (self.vm_uuid, self.disk_id), '%s.json' % self.snap_name)

    @classmethod
    def get_total_dc_size(cls, dc):
        """Return cumulative backup size for one DC"""
        key = cls.BACKUP_SIZE_TOTAL_DC_KEY % dc.id
        qs = cls.objects.filter(dc=dc).exclude(status__in=(cls.PENDING, cls.LOST), size__isnull=True)

        return get_cached_size(key, qs)

    @classmethod
    def get_total_vm_size(cls, vm):
        """Return cumulative backup size for one VM"""
        key = cls.BACKUP_SIZE_TOTAL_VM_KEY % vm.uuid
        qs = cls.objects.filter(vm=vm).exclude(status__in=(cls.PENDING, cls.LOST), size__isnull=True)

        return get_cached_size(key, qs)

    @classmethod
    def clear_total_dc_size(cls, dc):
        return clear_cached_size(cls.BACKUP_SIZE_TOTAL_DC_KEY % getattr(dc, 'id', dc))

    @classmethod
    def clear_total_vm_size(cls, vm):
        return clear_cached_size(cls.BACKUP_SIZE_TOTAL_VM_KEY % getattr(vm, 'uuid', vm))

    @classmethod
    def update_resources(cls, ns, vm, dc):
        """Update NodeStorage and Storage size_free"""
        ns.save(update_resources=True, update_dcnode_resources=True, recalculate_vms_size=False,
                recalculate_snapshots_size=False, recalculate_images_size=False, recalculate_backups_size=True,
                recalculate_dc_backups_size=(dc,))
        cls.clear_total_dc_size(dc)

        if vm:
            cls.clear_total_vm_size(vm)

    def update_zpool_resources(self):
        """Used by backup callback tasks"""
        # noinspection PyTypeChecker
        self.update_resources(self.zpool, self.vm, self.dc)  # Broken PyCharm inspection
