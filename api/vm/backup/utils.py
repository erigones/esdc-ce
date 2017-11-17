from django.db.utils import DatabaseError

from que.tasks import get_task_logger
from api.exceptions import ObjectNotFound, InvalidInput, APIError
from api.vm.snapshot.utils import filter_snap_define
from vms.models import Backup

logger = get_task_logger(__name__)

# A backup task can wait for a free backup worker for up to 4 hours (bug #chili-584)
BACKUP_TASK_EXPIRES = 14400

try:
    t_long = long
except NameError:
    t_long = int


# noinspection PyUnusedLocal
def get_backups(request, bkp_filter, data):
    """Return Backup queryset according to filter and backup names in data"""
    bkpnames = data.get('bkpnames', None)

    if not (bkpnames and isinstance(bkpnames, (list, tuple))):  # List and not empty
        raise InvalidInput('Invalid bkpnames')

    bkp_filter['name__in'] = bkpnames
    # TODO: check indexes
    bkps = Backup.objects.select_related('node', 'vm').filter(**bkp_filter)

    if not bkps:
        raise ObjectNotFound(model=Backup)

    bkp = bkps[0]
    for i in bkps:
        if i.node != bkp.node or i.vm != bkp.vm:
            raise InvalidInput('Invalid bkpnames')

    return bkps, bkpnames


def output_extended_backup_count(request, data):
    """Fetch extended boolean from GET request and prepare annotation dict"""
    if request.method == 'GET' and data and data.get('extended', False):
        # noinspection SqlDialectInspection,SqlNoDataSourceInspection
        return {'backups': 'SELECT COUNT(*) FROM "vms_backup" WHERE '
                           '"vms_backup"."define_id" = "vms_backupdefine"."id"'}
    else:
        return None


def filter_backup_define(query_filter, data):
    """Validate backup definition and update dictionary used for queryset filtering"""
    return filter_snap_define(query_filter, data)


def get_backup_cmd(action, bkp, bkps=None, define=None, zfs_filesystem=None, fsfreeze=None, vm=None):  # noqa: R701
    """Return backup command suitable for execute()"""
    if bkp.type == Backup.DATASET:
        action_prefix = 'ds'
        file_backup = False
    elif bkp.type == Backup.FILE:
        action_prefix = 'file'
        file_backup = True
    else:
        raise APIError('Invalid backup type')

    vm = vm or bkp.vm

    if vm and bkp.node != vm.node:
        cmd_args = ['-H %s' % vm.node.address]
    else:
        cmd_args = []

    if action == 'create':
        if file_backup:
            cmd_args.append('-f "%s" -s %s -m "%s" -j -' % (bkp.create_file_path(), zfs_filesystem,
                                                            bkp.create_file_manifest_path()))

            if define.compression:
                cmd_args.append('-c %s' % define.get_compression_display())
        else:
            cmd_args.append('-d %s -s %s@%s -n "%s" -m "%s" -j -' % (bkp.create_dataset_path(), zfs_filesystem,
                                                                     bkp.snap_name, bkp.name,
                                                                     bkp.create_dataset_manifest_path()))

        if define.bwlimit:
            cmd_args.append('-l %d' % define.bwlimit)

        if fsfreeze:
            cmd_args.append('-F "%s"' % fsfreeze)

    elif action == 'delete':
        if bkps:
            to_delete = ' '.join(['"%s"' % b.file_path for b in bkps])
        else:
            to_delete = '"%s"' % bkp.file_path

        if file_backup:
            cmd_args = ['-f %s' % to_delete]
        else:
            cmd_args.append('-s %s' % to_delete)

            if vm:
                if bkps:
                    last = ' '.join(['%s@%s' % (b.zfs_filesystem_real, b.snap_name) for b in bkps if b.last])
                elif bkp.last:
                    last = '%s@%s' % (bkp.zfs_filesystem_real, bkp.snap_name)
                else:
                    last = None

                if last:
                    cmd_args.append('-r %s' % last)

        if bkp.manifest_path:
            cmd_args.append('-m "%s"' % bkp.manifest_path)

    elif action == 'restore':
        if file_backup:
            cmd_args.append('-f "%s" -d %s -c %s' % (bkp.file_path, zfs_filesystem, bkp.checksum))
        else:
            cmd_args.append('-s %s -d %s' % (bkp.file_path, zfs_filesystem))

    else:
        raise APIError('Invalid backup action')

    return 'esbackup %s-%s %s' % (action_prefix, action, ' '.join(cmd_args))


def is_backup_task_running(obj):
    """Return True if a PUT/POST/DELETE backup task is running for a VM"""
    bkp_tasks = obj.get_tasks(match_dict={'view': 'vm_backup'})
    bkp_tasks.update(obj.get_tasks(match_dict={'view': 'vm_backup_list'}))

    return any(t.get('method', '').upper() in ('POST', 'PUT', 'DELETE') for t in bkp_tasks.values())


def sync_backups(db_backups, node_snaps):
    """Sync DB status of dataset backups with real information from compute node.
    Used by PUT vm_snapshot_list and PUT node_vm_snapshot_list."""
    lost = 0

    for bkp in db_backups:
        if bkp.type == bkp.FILE:
            continue

        bkp_snap_name = bkp.snap_name

        try:
            if bkp_snap_name in node_snaps:
                if bkp.status == bkp.LOST:
                    logger.warn('Backup %s (ID %s) found, changing status to OK', bkp, bkp.id)
                    bkp.status = bkp.OK
                    bkp.size = t_long(node_snaps[bkp_snap_name][1])
                    bkp.save(update_fields=('status', 'status_change', 'size'), force_update=True)
                else:
                    logger.debug('Backup %s (ID %s) is OK', bkp, bkp.id)
                    if bkp.locked:  # PENDING or ROLLBACK status
                        logger.warn('Backup %s (ID %s) is OK on compute node, but in %s status since %s',
                                    bkp, bkp.id, bkp.get_status_display(), bkp.status_change)
                        if is_backup_task_running(bkp.vm or bkp.node):
                            logger.warn('Ignoring backup %s (ID %s) because a snapshot task is running on node %s',
                                        bkp, bkp.id, bkp.node)
                        else:
                            logger.warn('Changing backup %s (ID %s) status to OK', bkp, bkp.id)
                            bkp.status = bkp.OK
                            bkp.save(update_fields=('status', 'status_change'), force_update=True)
            else:
                logger.warn('Backup %s (ID %s) does not exist on compute node', bkp, bkp.id)
                if is_backup_task_running(bkp.vm or bkp.node):
                    logger.warn('Ignoring backup %s (ID %s) because a backup task is running on node %s',
                                bkp, bkp.id, bkp.node)
                    continue
                if bkp.status != bkp.LOST:
                    bkp.status = bkp.LOST
                    bkp.save(update_fields=('status', 'status_change'), force_update=True)
                    lost += 1
                continue
        except DatabaseError:
            logger.warn('Backup %s (ID %s) could not be updated (maybe it vanished)', bkp, bkp.id)

        node_snaps.pop(bkp_snap_name, None)

    return lost
