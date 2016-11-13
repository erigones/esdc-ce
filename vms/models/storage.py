from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core.cache import cache
import decimal

# noinspection PyProtectedMember
from vms.models.base import _VirtModel, _UserTasksModel
from vms.models.dc import Dc

try:
    t_long = long
except NameError:
    t_long = int

EMPTY = ()


def b_to_mb(value):
    return t_long(value) / 1048576


def _calculate_vms_size(ns, dc=None):
    """Used in node_storage.get_vms_size()"""
    res = 0
    qs = ns.node.vm_set

    if dc:
        qs = qs.filter(dc=dc)

    for vm in qs.all():
        res += vm.get_disk_size(zpool=ns.zpool)

    return res


def _calculate_snapshots_size(ns, snap_model=None, dc=None):
    """Used in node_storage.get_snapshots_size()"""
    qs = ns.snapshot_set.exclude(status__in=(snap_model.PENDING, snap_model.LOST), size__isnull=True)

    if dc:
        qs = qs.filter(vm__dc=dc)

    size = qs.aggregate(models.Sum('size')).get('size__sum')

    if size:
        return b_to_mb(size)
    else:
        return 0


def _calculate_backups_size(ns, backup_model=None, dc=None):
    """Used in node_storage.get_backups_size()"""
    qs = ns.backup_set.exclude(status__in=(backup_model.PENDING, backup_model.LOST), size__isnull=True)

    if dc:
        qs = qs.filter(dc=dc)

    size = qs.aggregate(models.Sum('size')).get('size__sum')

    if size:
        return b_to_mb(size)
    else:
        return 0


def _calculate_images_size(ns):
    """Used in node_storage.get_images_size()"""
    return ns.images.all().aggregate(models.Sum('size')).get('size__sum', 0)


def get_cached_size(key, qs, timeout=300):
    """Return cached size sum obtained from queryset"""
    size = cache.get(key)

    if size is None:
        size = qs.aggregate(models.Sum('size')).get('size__sum')

        if size:
            size = b_to_mb(size)
        else:
            size = 0

        cache.set(key, size, timeout)

    return size


def clear_cached_size(key):
    """Remove size info from cache"""
    return cache.delete(key)


class Storage(_VirtModel):
    """
    Storage = zpool.
    """
    ACCESS = (
        (_VirtModel.PUBLIC, _('Public')),
        (_VirtModel.PRIVATE, _('Private')),
    )

    LOCAL = 1
    NFS = 2
    ISCSI = 3
    FIBER = 4
    TYPE = (
        (LOCAL, _('Local')),
        # (NFS, _('NFS')),
        (ISCSI, _('iSCSI')),
        (FIBER, _('Fiber Channel')),
    )

    SIZE_COEF = '0.6'

    # Inherited: id, name (=zpool@node), alias (=zpool), owner, desc, access, created, changed
    type = models.SmallIntegerField(_('Storage type'), choices=TYPE, default=LOCAL)
    size = models.PositiveIntegerField(_('Disk pool size (MB)'), default=0)
    size_coef = models.DecimalField(_('Disk pool size coefficient'), max_digits=4, decimal_places=2, default=SIZE_COEF,
                                    help_text=_('Coefficient for calculating the maximum amount of '
                                                'disk space for virtual machines.'))
    size_free = models.IntegerField(_('Free disk pool size (MB)'), default=0, editable=False)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Storage')
        verbose_name_plural = _('Storages')

    @property
    def zpool(self):
        return self.alias

    @property
    def size_total(self):
        # We are working with decimal objects and rounding everything down
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        return int(int(self.size) * float(self.size_coef))


class NodeStorage(models.Model, _UserTasksModel):
    """
    Storage <-> Node association
    """
    _pk_key = 'nodestorage_id'  # _UserTasksModel
    _dc_node = None  # Related DcNode cache
    _dc = None  # Dc object used to simplify API/GUI views

    zpool = models.CharField(_('Zpool'), max_length=64, db_index=True)
    node = models.ForeignKey('vms.Node', verbose_name=_('Compute node'))
    storage = models.ForeignKey(Storage, verbose_name=_('Storage'))
    dc = models.ManyToManyField(Dc, verbose_name=_('Datacenter'), blank=True)
    images = models.ManyToManyField('vms.Image', verbose_name=_('Images'), blank=True)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Storage')
        verbose_name_plural = _('Storages')
        unique_together = (('node', 'zpool'),)

    def __unicode__(self):
        return '%s' % self.zpool

    @property
    def alias(self):  # task log requirement
        return '%s@%s' % (self.storage.alias, self.node.hostname)

    @property
    def name(self):  # task log requirement
        return '%s@%s' % (self.zpool, self.node.hostname)

    @property
    def owner(self):  # task log requirement
        return self.storage.owner

    @classmethod
    def get_log_name_lookup_kwargs(cls, log_name_value):
        """task log requirement"""
        try:
            zpool, node_hostname = log_name_value.split('@', 1)
        except ValueError:
            return {'zpool': log_name_value}
        else:
            return {'zpool': zpool, 'node__hostname': node_hostname}

    def _get_related_object_size(self, key, fetch_size_fun, clear_cache=False, **fetch_fun_kwargs):
        if not self.pk:
            return 0

        res = cache.get(key)

        if clear_cache or res is None:
            res = fetch_size_fun(self, **fetch_fun_kwargs)
            cache.set(key, res)

        return int(res)

    def get_vms_size(self, clear_cache=False):
        """Return cumulative size for all servers from VM parameters which are using this storage"""
        from vms.models.node import Node
        key = Node.VMS_SIZE_TOTAL_KEY % self.pk

        return self._get_related_object_size(key, _calculate_vms_size, clear_cache=clear_cache)

    @property
    def size_vms(self):
        """Return total size of VM disks (MB) stored on this node zpool. Use cache if possible."""
        return self.get_vms_size()

    def get_dc_vms_size(self, dc, clear_cache=False):
        """Return total size for all servers in one DC which are using this storage"""
        from vms.models.node import Node
        key = Node.VMS_SIZE_DC_KEY % (dc.pk, self.pk)
        res = self._get_related_object_size(key, _calculate_vms_size, clear_cache=clear_cache, dc=dc)

        if clear_cache:
            # Recalculate cumulative size of all VMs in DC by summing sizes from all node storages
            total = res + sum(ns.get_dc_vms_size(dc) for ns in self.__class__.objects.exclude(pk=self.pk).filter(dc=dc))
            cache.set(dc.VMS_SIZE_TOTAL_DC_KEY % dc.pk, total)

        return res

    @property
    def size_dc_vms(self):
        return self.get_dc_vms_size(self._dc)

    def get_snapshots_size(self, clear_cache=False):
        """Return total size of snapshots (MB) stored on this node zpool"""
        from vms.models.snapshot import Snapshot
        key = Snapshot.SNAPSHOT_SIZE_TOTAL_KEY % self.pk

        return self._get_related_object_size(key, _calculate_snapshots_size, clear_cache=clear_cache,
                                             snap_model=Snapshot)

    @property
    def size_snapshots(self):
        """Return total size of snapshots (MB) stored on this node zpool. Use cache if possible."""
        return self.get_snapshots_size()

    def get_rep_snapshots_size(self):
        """Return total size of replicated snapshots (MB) stored on this node zpool"""
        from vms.models.snapshot import Snapshot
        key = Snapshot.REP_SNAPSHOT_SIZE_TOTAL_KEY % self.pk

        return cache.get(key) or 0

    def set_rep_snapshots_size(self, size):
        """Save total size of replicated snapshots coming from api.node.snapshot.tasks.node_vm_snapshot_sync_cb"""
        from vms.models.snapshot import Snapshot
        key = Snapshot.REP_SNAPSHOT_SIZE_TOTAL_KEY % self.pk
        cache.set(key, b_to_mb(size))

    @property
    def size_rep_snapshots(self):
        """Return total size of replicated snapshots (MB) stored on this node zpool"""
        return self.get_rep_snapshots_size()

    def get_dc_snapshots_size(self, dc, clear_cache=False):
        """Return total size of snapshots (MB) in a datacenter stored on this node zpool"""
        from vms.models.snapshot import Snapshot
        key = Snapshot.SNAPSHOT_SIZE_DC_KEY % (dc.pk, self.pk)

        return self._get_related_object_size(key, _calculate_snapshots_size, clear_cache=clear_cache,
                                             snap_model=Snapshot, dc=dc)

    @property
    def size_dc_snapshots(self):
        return self.get_dc_snapshots_size(self._dc)

    def get_backups_size(self, clear_cache=False):
        """Return total size of backups (MB) stored on this node zpool"""
        from vms.models.backup import Backup
        key = Backup.BACKUP_SIZE_TOTAL_KEY % self.pk

        return self._get_related_object_size(key, _calculate_backups_size, clear_cache=clear_cache,
                                             backup_model=Backup)

    @property
    def size_backups(self):
        """Return total size of backups (MB) stored on this node zpool. Use cache if possible."""
        return self.get_backups_size()

    def get_dc_backups_size(self, dc, clear_cache=False):
        """Return total size of backups (MB) in a datacenter stored on this node zpool"""
        from vms.models.backup import Backup
        key = Backup.BACKUP_SIZE_DC_KEY % (dc.pk, self.pk)

        return self._get_related_object_size(key, _calculate_backups_size, clear_cache=clear_cache,
                                             backup_model=Backup, dc=dc)

    @property
    def size_dc_backups(self):
        return self.get_dc_backups_size(self._dc)

    def get_images_size(self, clear_cache=False):
        """Return cumulative size for all disk images stored on this node storage"""
        from vms.models.image import Image
        key = Image.IMAGE_SIZE_TOTAL_KEY % self.pk

        return self._get_related_object_size(key, _calculate_images_size, clear_cache=clear_cache)

    @property
    def size_images(self):
        """Return total size of images (MB) stored on this node zpool. Use cache if possible."""
        return self.get_images_size()

    def get_size_free(self, dc_node):
        """Return disk free space from dc node if storage is a default local one (zones)"""
        if dc_node and self.zpool == self.node.zpool:
            return dc_node.disk_free
        return self.storage.size_free

    def get_size(self, dc_node):
        """Return disk size from dc node if storage is a default local one (zones)"""
        if dc_node and self.zpool == self.node.zpool:
            return dc_node.disk
        return self.storage.size_total
    get_size_total = get_size

    def set_dc_node(self, dc_node):
        """Used by size and size_free properties"""
        self._dc_node = dc_node

    def set_dc(self, dc):
        """Used by size_dc_vms and size_dc_backups properties"""
        self._dc = dc

    @property
    def size_free(self):
        return self.get_size_free(self._dc_node)

    @property
    def size(self):
        return self.get_size(self._dc_node)
    size_total = size

    @property
    def web_data(self):
        """Return dict used in html templates"""
        return {
            'node': self.node.hostname,
            'zpool': self.zpool,
            'type': self.storage.type,
            'alias': self.storage.alias,
            'owner': self.storage.owner.username,
            'access': self.storage.access,
            'size_coef': str(self.storage.size_coef),
            'desc': self.storage.desc,
        }

    # noinspection PyUnusedLocal
    def get_free_size(self, recalculate_vms_size=True, recalculate_snapshots_size=True,
                      recalculate_backups_size=True, recalculate_images_size=True):
        """Count free storage size"""
        used = self.get_vms_size(clear_cache=recalculate_vms_size) + \
            self.get_snapshots_size(clear_cache=recalculate_snapshots_size) + self.get_rep_snapshots_size() + \
            self.get_backups_size(clear_cache=recalculate_backups_size)
        # self.get_images_size(clear_cache=recalculate_images_size)  # TODO: fix images_size implementation

        return int(self.storage.size_total) - used

    def update_resources(self, save=True, recalculate_dc_vms_size=EMPTY, recalculate_dc_snapshots_size=EMPTY,
                         recalculate_dc_backups_size=EMPTY, **kwargs):
        """Update free storage size"""
        self.storage.size_free = self.get_free_size(**kwargs)

        for dc in recalculate_dc_vms_size:
            self.get_dc_vms_size(dc, clear_cache=True)

        for dc in recalculate_dc_snapshots_size:
            self.get_dc_snapshots_size(dc, clear_cache=True)

        for dc in recalculate_dc_backups_size:
            self.get_dc_backups_size(dc, clear_cache=True)

        if save:
            self.storage.save()

    def save(self, update_resources=True, update_dcnode_resources=False, recalculate_vms_size=True,
             recalculate_dc_vms_size=EMPTY, recalculate_snapshots_size=True, recalculate_dc_snapshots_size=EMPTY,
             recalculate_backups_size=True, recalculate_dc_backups_size=EMPTY, recalculate_images_size=True, **kwargs):
        if update_resources:
            self.update_resources(recalculate_vms_size=recalculate_vms_size,
                                  recalculate_dc_vms_size=recalculate_dc_vms_size,
                                  recalculate_snapshots_size=recalculate_snapshots_size,
                                  recalculate_dc_snapshots_size=recalculate_dc_snapshots_size,
                                  recalculate_backups_size=recalculate_backups_size,
                                  recalculate_dc_backups_size=recalculate_dc_backups_size,
                                  recalculate_images_size=recalculate_images_size)

        ret = super(NodeStorage, self).save(**kwargs)

        if update_resources and update_dcnode_resources:
            from vms.models.node import DcNode
            DcNode.update_all(node=self.node)

        return ret

    def check_free_space(self, disk_size):
        """Return True if it is possible to allocate VM disks on this storage"""
        return disk_size <= self.storage.size_free

    # noinspection PyUnusedLocal
    @staticmethod
    def post_delete(sender, instance, **kwargs):
        """Cleanup storage"""
        if instance.storage:
            instance.storage.delete()

    def is_node_image_running(self):
        """Return appropriate tasks for node_image view/task for this NodeStorage"""
        return self.get_tasks(match_dict={'view': 'node_image'})
