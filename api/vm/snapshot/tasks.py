from django.db.utils import DatabaseError

from vms.models import Vm, Snapshot, SnapshotDefine
from que.tasks import cq, get_task_logger
from que.mgmt import MgmtCallbackTask
from que.utils import task_id_from_task_id
from que.exceptions import TaskException
from api.status import HTTP_423_LOCKED
from api.decorators import catch_exception
from api.utils.request import get_dummy_request
from api.utils.views import call_api_view
from api.task.utils import callback, task_log_error, get_task_error_message
from api.task.tasks import task_log_cb_success
from api.task.response import to_string
from api.vm.messages import LOG_SNAP_CREATE, LOG_SNAPS_DELETE
from api.mon.zabbix import Zabbix

__all__ = ('vm_snapshot_list_cb', 'vm_snapshot_cb', 'vm_snapshot_beat', 'vm_snapshot_sync_cb')

logger = get_task_logger(__name__)

try:
    t_long = long
except NameError:
    t_long = int


# noinspection PyUnusedLocal
def _vm_snapshot_list_cb_failed(result, task_id, snaps, action):
    """Callback helper for failed task - revert snapshot statuses"""
    if action == 'DELETE':
        snaps.update(status=Snapshot.OK)


# noinspection PyUnusedLocal
def _vm_snapshot_cb_failed(result, task_id, snap, action):
    """Callback helper for failed task - revert snapshot status"""
    if action == 'POST':
        snap.delete()
    elif action == 'PUT':
        snap.status = snap.OK
        snap.save_status()
        snap.vm.revert_notready()
    elif action == 'DELETE':
        snap.status = snap.OK
        snap.save_status()


@catch_exception
def _delete_oldest(model, define, view_function, view_item, task_id, msg):
    """
    Helper for finding oldest snapshots/backups and running DELETE view_function().

    @type model: django.db.models.Model
    """
    vm = define.vm
    # TODO: check indexes
    total = model.objects.filter(vm=vm, disk_id=define.disk_id, define=define, status=model.OK).count()
    to_delete = total - define.retention

    if to_delete < 1:
        return None

    # List of snapshot or backup names to delete TODO: check indexes
    oldest = model.objects.filter(vm=vm, disk_id=define.disk_id, define=define, status=model.OK)\
        .values_list('name', flat=True).order_by('id')[:to_delete]
    view_name = view_function.__name__
    view_data = {'disk_id': define.array_disk_id, view_item: tuple(oldest)}
    request = get_dummy_request(vm.dc, method='DELETE', system_user=True)
    request.define_id = define.id  # Automatic task
    # Go!
    logger.info('Running DELETE %s(%s, %s), because %s>%s', view_name, vm, view_data, total, define.retention)
    res = call_api_view(request, 'DELETE', view_function, vm.hostname, data=view_data)

    if res.status_code in (200, 201):
        logger.warn('DELETE %s(%s, %s) was successful: %s', view_name, vm, view_data, res.data)
    else:
        logger.error('Running DELETE %s(%s, %s) failed: %s (%s): %s', view_name, vm, view_data,
                     res.status_code, res.status_text, res.data)
        Zabbix.vm_send_alert(vm, 'Automatic deletion of old %ss %s/disk-%s failed to start.' % (
            model.__name__.lower(), vm.hostname, define.array_disk_id))
        # Need to log this, because nobody else does (+ there is no PENDING task)
        detail = 'hostname=%s, %s=%s, disk_id=%s, Error: %s' % (vm.hostname, view_item, ','.join(oldest),
                                                                define.array_disk_id, get_task_error_message(res.data))
        task_log_error(task_id, msg, vm=vm, detail=detail, update_user_tasks=False)

    return res


@cq.task(name='api.vm.snapshot.tasks.vm_snapshot_list_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_snapshot_list_cb(result, task_id, vm_uuid=None, snap_ids=None):
    """
    A callback function for DELETE api.vm.snapshot.views.vm_snapshot_list.
    """
    snaps = Snapshot.objects.filter(id__in=snap_ids)
    action = result['meta']['apiview']['method']

    if result['returncode'] == 0:
        vm = snaps[0].vm
        if action == 'DELETE':
            snaps.delete()
            result['message'] = 'Snapshots successfully deleted'

    else:
        _vm_snapshot_list_cb_failed(result, task_id, snaps, action)
        msg = result.get('message', '')
        logger.error('Found nonzero returncode in result from %s vm_snapshot_list(%s, %s). Error: %s',
                     action, vm_uuid, snaps, msg)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg))

    task_log_cb_success(result, task_id, vm=vm, **result['meta'])
    return result


# noinspection PyUnusedLocal,PyUnusedLocal,PyUnusedLocal
def _vm_snapshot_cb_alert(result, task_id, snap_id=None, task_exception=None, **kwargs):
    """Alert function for failed snapshot creation"""
    action = result['meta']['apiview']['method']

    if action == 'POST':
        action_msg = 'created'
    elif action == 'DELETE':
        action_msg = 'deleted'
    else:
        return  # Alert only failed creation and deletion

    snap = getattr(task_exception, 'snap', None)
    if not snap:
        snap = Snapshot.objects.select_related('vm').get(id=snap_id)

    if snap.type == Snapshot.AUTO:
        vm = snap.vm
        if vm:
            Zabbix.vm_send_alert(vm, 'Automatic snapshot %s of server %s@disk-%s could not be %s.' % (
                snap.name, vm.hostname, snap.array_disk_id, action_msg))


@cq.task(name='api.vm.snapshot.tasks.vm_snapshot_cb', base=MgmtCallbackTask, bind=True)
@callback(error_fun=_vm_snapshot_cb_alert)
def vm_snapshot_cb(result, task_id, vm_uuid=None, snap_id=None):
    """
    A callback function for api.vm.snapshot.views.vm_snapshot.
    """
    snap = Snapshot.objects.select_related('vm').get(id=snap_id)
    vm = snap.vm
    action = result['meta']['apiview']['method']
    msg = result.get('message', '')

    if result['returncode'] == 0:
        if msg:
            result['detail'] = 'msg=' + to_string(msg)
        else:
            result['detail'] = ''

        if action == 'POST':
            snap.status = snap.OK
            result['message'] = 'Snapshot successfully created'

            if snap.fsfreeze:
                if 'freeze failed' in msg:
                    snap.fsfreeze = False
                    result['message'] += ' (filesystem freeze failed)'
                    Zabbix.vm_send_alert(vm, 'Snapshot %s of server %s@disk-%s was created, but filesystem '
                                             'freeze failed.' % (snap.name, vm.hostname, snap.array_disk_id),
                                         priority=Zabbix.zbx.WARNING)

            snap.save(update_fields=('status', 'fsfreeze'))

            if snap.define and snap.define.retention:  # Retention - delete oldest snapshot
                assert vm == snap.define.vm
                assert snap.disk_id == snap.define.disk_id
                from api.vm.snapshot.views import vm_snapshot_list
                _delete_oldest(Snapshot, snap.define, vm_snapshot_list, 'snapnames', task_id, LOG_SNAPS_DELETE)

        elif action == 'PUT':
            snap.status = snap.OK
            snap.save_status()
            if result['meta']['apiview']['force']:
                # TODO: check indexes
                Snapshot.objects.filter(vm=vm, disk_id=snap.disk_id, id__gt=snap.id).delete()
            vm.revert_notready()
            result['message'] = 'Snapshot successfully restored'

        elif action == 'DELETE':
            snap.delete()
            result['message'] = 'Snapshot successfully deleted'

    else:
        _vm_snapshot_cb_failed(result, task_id, snap, action)  # Delete snapshot or update snapshot status
        logger.error('Found nonzero returncode in result from %s vm_snapshot(%s, %s). Error: %s',
                     action, vm_uuid, snap, msg)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg), snap=snap)

    task_log_cb_success(result, task_id, vm=vm, **result['meta'])
    return result


@cq.task(name='api.vm.snapshot.tasks.vm_snapshot_beat')
def vm_snapshot_beat(snap_define_id):
    """
    This is a periodic beat task. Run POST vm_snapshot according to snapshot definition.
    """
    from api.vm.snapshot.views import vm_snapshot

    snap_define = SnapshotDefine.objects.get(id=snap_define_id)
    snap_name = snap_define.generate_snapshot_name()
    vm = snap_define.vm
    disk_id = snap_define.array_disk_id
    request = get_dummy_request(vm.dc, method='POST', system_user=True)
    request.define_id = snap_define.id  # Automatic task
    # Go!
    res = call_api_view(request, 'POST', vm_snapshot, vm.hostname, snap_name, data={'disk_id': disk_id,
                                                                                    'fsfreeze': snap_define.fsfreeze})

    if res.status_code == 201:
        logger.info('POST vm_snapshot(%s, %s, {disk_id=%s}) was successful: %s',
                    vm, snap_name, disk_id, res.data)
    else:
        # Need to log this, because nobody else does (+ there is no PENDING task)
        detail = 'snapname=%s, disk_id=%s, type=%s. Error: %s' % (snap_name, disk_id, Snapshot.AUTO,
                                                                  get_task_error_message(res.data))
        task_log_error(task_id_from_task_id(vm_snapshot_beat.request.id, dc_id=vm.dc.id),
                       LOG_SNAP_CREATE, vm=vm, detail=detail, update_user_tasks=False)

        if res.status_code == HTTP_423_LOCKED:
            logger.warning('Running POST vm_snapshot(%s, %s, {disk_id=%s}) failed: %s (%s): %s',
                           vm, snap_name, disk_id, res.status_code, res.status_text, res.data)
        else:
            logger.error('Running POST vm_snapshot(%s, %s, {disk_id=%s}) failed: %s (%s): %s',
                         vm, snap_name, disk_id, res.status_code, res.status_text, res.data)
            Zabbix.vm_send_alert(vm, 'Automatic snapshot %s/disk-%s@%s failed to start.' % (vm.hostname, disk_id,
                                                                                            snap_define.name))


def _parse_snapshot_list_line(line):
    line = line.split()
    return line[0].strip().split('@', 1)[1], line[1:]


def parse_node_snaps(data):
    """Parse output from esnapshot list"""
    return dict(_parse_snapshot_list_line(line) for line in data.strip().split('\n') if line)


def is_snapshot_task_running(vm):
    """Return True if a PUT/POST/DELETE snapshot task is running for a VM"""
    snap_tasks = vm.get_tasks(match_dict={'view': 'vm_snapshot'})
    snap_tasks.update(vm.get_tasks(match_dict={'view': 'vm_snapshot_list'}))

    return any(t.get('method', '').upper() in ('POST', 'PUT', 'DELETE') for t in snap_tasks.values())


def sync_snapshots(db_snaps, node_snaps):
    """Sync snapshot DB status and size with real information from compute node.
    Used by PUT vm_snapshot_list and PUT node_vm_snapshot_list."""
    lost = 0

    for snap in db_snaps:
        snap_zfs_name = snap.zfs_name

        try:
            if snap_zfs_name in node_snaps:
                if snap.status == snap.LOST:
                    logger.warn('Snapshot %s (ID %s) found, changing status to OK', snap, snap.id)
                    snap.status = snap.OK
                    snap.size = t_long(node_snaps[snap_zfs_name][1])
                    snap.save(update_fields=('status', 'status_change', 'size'), force_update=True)
                else:
                    logger.debug('Snapshot %s (ID %s) is OK', snap, snap.id)
                    snap_size = t_long(node_snaps[snap_zfs_name][1])
                    if snap.size != snap_size:
                        snap.size = snap_size
                        snap.save(update_fields=('size',), force_update=True)
                    if snap.locked:  # PENDING or ROLLBACK status
                        logger.warn('Snapshot %s (ID %s) is OK on compute node, but in %s status since %s',
                                    snap, snap.id, snap.get_status_display(), snap.status_change)
                        if is_snapshot_task_running(snap.vm):
                            logger.warn('Ignoring snapshot %s (ID %s) because a snapshot task is running for VM %s',
                                        snap, snap.id, snap.vm)
                        else:
                            logger.warn('Changing snapshot %s (ID %s) status to OK', snap, snap.id)
                            snap.status = snap.OK
                            snap.save(update_fields=('status', 'status_change'), force_update=True)
            else:
                logger.warn('Snapshot %s (ID %s) does not exist on compute node', snap, snap.id)
                if is_snapshot_task_running(snap.vm):
                    logger.warn('Ignoring snapshot %s (ID %s) because a snapshot task is running for VM %s',
                                snap, snap.id, snap.vm)
                    continue
                if snap.status != snap.LOST:
                    snap.status = snap.LOST
                    snap.save(update_fields=('status', 'status_change', 'size'), force_update=True)
                    lost += 1
                continue
        except DatabaseError:
            logger.warn('Snapshot %s (ID %s) could not be updated (maybe it vanished)', snap, snap.id)

        node_snaps.pop(snap_zfs_name, None)

    return lost


@cq.task(name='api.vm.snapshot.tasks.vm_snapshot_sync_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_snapshot_sync_cb(result, task_id, vm_uuid=None, disk_id=None):
    """
    A callback function for PUT api.vm.snapshot.views.vm_snapshot_list a.k.a. vm_snapshot_sync.
    """
    vm = Vm.objects.select_related('dc').get(uuid=vm_uuid)
    data = result.pop('data', '')

    if result['returncode'] != 0:
        msg = result.get('message', '') or data
        logger.error('Found nonzero returncode in result from PUT vm_snapshot_list(%s). Error: %s', vm_uuid, msg)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg))

    node_snaps = parse_node_snaps(data)
    logger.info('Found %d snapshots for VM %s on disk ID %s', len(node_snaps), vm, disk_id)
    lost = sync_snapshots(vm.snapshot_set.select_related('vm').filter(disk_id=disk_id).all(), node_snaps)

    # Remaining snapshots on compute node are internal or old lost snapshots which do not exist in DB
    # remaining es- and as- snapshots must be created in DB; some is- and rs- could be probably removed, but
    # these are hard to determine, so we are ignoring them
    snap_prefix = Snapshot.USER_PREFIX
    new_snaps = {snap: node_snaps.pop(snap) for snap in tuple(node_snaps.keys()) if snap.startswith(snap_prefix)}

    ns = vm.get_node_storage(disk_id)

    if new_snaps:
        logger.warn('VM %s has following snapshots on disk ID %s, which are not defined in DB: %s',
                    vm, disk_id, new_snaps.keys())

        for zfs_name, info in new_snaps.items():
            try:
                name = info[2]
                if not name:
                    raise IndexError
            except IndexError:
                name = info[0]

            try:
                Snapshot.create_from_zfs_name(zfs_name, name=name, timestamp=int(info[0]), vm=vm, disk_id=disk_id,
                                              zpool=ns, size=t_long(info[1]), note='Found by snapshot sync')
            except Exception as exc:
                logger.error('Could not recreate snapshot %s (vm=%s, disk_id=%s). Error: %s',
                             zfs_name, vm, disk_id, exc)
            else:
                logger.warn('Recreated snapshot %s (vm=%s, disk_id=%s)', zfs_name, vm, disk_id)

    logger.info('VM %s has following internal/service snapshots on disk ID %s: %s', vm, disk_id, node_snaps.keys())
    # Update node storage snapshot size counters
    Snapshot.update_resources(ns, vm)

    try:
        # Update last flag on dataset backups
        bkp_ids = [snap[3:] for snap in node_snaps if snap.startswith('is-')]
        if bkp_ids:
            vm.backup_set.filter(disk_id=disk_id, id__in=bkp_ids).update(last=True)
            vm.backup_set.filter(disk_id=disk_id, last=True).exclude(id__in=bkp_ids).update(last=False)
        else:
            vm.backup_set.filter(disk_id=disk_id, last=True).update(last=False)
    except Exception as exc:
        logger.exception(exc)

    msg = 'Snapshots successfully synced'
    if lost:
        msg += '; WARNING: %d snapshot(s) lost' % lost
    if new_snaps:
        msg += '; WARNING: %d snapshot(s) found' % len(new_snaps)

    result['message'] = msg
    task_log_cb_success(result, task_id, vm=vm, **result['meta'])
    return result
