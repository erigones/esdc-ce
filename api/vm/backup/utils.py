from api.exceptions import ObjectNotFound, InvalidInput, APIError
from api.vm.snapshot.utils import filter_snap_define
from vms.models import Backup

# A backup task can wait for a free backup worker for up to 4 hours (bug #chili-584)
BACKUP_TASK_EXPIRES = 14400


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
        return {'backups': 'SELECT COUNT(*) FROM "vms_backup" WHERE '
                           '"vms_backup"."define_id" = "vms_backupdefine"."id"'}
    else:
        return None


def filter_backup_define(query_filter, data):
    """Validate backup definition and update dictionary used for queryset filtering"""
    return filter_snap_define(query_filter, data)


def get_backup_cmd(action, bkp, bkps=None, define=None, zfs_filesystem=None, fsfreeze=None, vm=None):
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
            cmd_args.append('-f "%s" -s %s' % (bkp.create_file_path(), zfs_filesystem))

            if define.compression:
                cmd_args.append('-c %s' % define.get_compression_display())
        else:
            cmd_args.append('-d %s -s %s@%s -n "%s"' % (bkp.create_dataset_path(), zfs_filesystem, bkp.snap_name,
                                                        bkp.name))

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

    elif action == 'restore':
        if file_backup:
            cmd_args.append('-f "%s" -d %s -c %s' % (bkp.file_path, zfs_filesystem, bkp.checksum))
        else:
            cmd_args.append('-s %s -d %s' % (bkp.file_path, zfs_filesystem))

    else:
        raise APIError('Invalid backup action')

    return 'esbackup %s-%s %s' % (action_prefix, action, ' '.join(cmd_args))
