from django.utils.six import iteritems

from vms.models import Vm, Snapshot, Backup, BackupDefine
from que.tasks import cq, get_task_logger
from que.mgmt import MgmtCallbackTask
from que.utils import task_id_from_task_id
from que.exceptions import TaskException
from api.utils.request import get_dummy_request
from api.utils.views import call_api_view
from api.status import HTTP_423_LOCKED
from api.decorators import catch_exception
from api.task.utils import callback, task_log_error, get_task_error_message
from api.task.tasks import task_log_cb_success
from api.task.response import to_string
from api.vm.messages import LOG_BKP_CREATE, LOG_BKPS_DELETE
# noinspection PyProtectedMember
from api.vm.snapshot.tasks import _delete_oldest
from api.mon.zabbix import Zabbix

__all__ = ('vm_backup_list_cb', 'vm_backup_cb', 'vm_backup_beat')

logger = get_task_logger(__name__)

BACKUP_LOG_DETAIL = frozenset(['msg', 'rc', 'time_elapsed', 'size', 'backup_snapshot_size'])


def _vm_backup_cb_detail(data):
    """Create tasklog detail - used by vm_backup_cb and vm_backup_list_cb"""
    return ', '.join(['%s=%s' % (k, to_string(v)) for k, v in iteritems(data) if k in BACKUP_LOG_DETAIL])


# noinspection PyUnusedLocal
def _vm_backup_list_cb_failed(result, task_id, bkps, action):
    """Callback helper for failed task - revert backup statuses"""
    if action == 'DELETE':
        bkps.update(status=Backup.OK)


# noinspection PyUnusedLocal
def _vm_backup_cb_failed(result, task_id, bkp, action, vm=None):
    """Callback helper for failed task - revert backup status"""
    if action == 'POST':
        bkp.delete()
        bkp.update_zpool_resources()
    elif action == 'PUT':
        bkp.status = bkp.OK
        bkp.save_status()
        vm.revert_notready()
    elif action == 'DELETE':
        bkp.status = bkp.OK
        bkp.save_status()


@catch_exception
def _vm_backup_deleted_last_snapshot_names(data):
    """deleted_last_snapshot_names is a list of removed snapshots from source/VM dataset"""
    deleted_last_snapshot_names = data.get('deleted_last_snapshot_names', None)

    if deleted_last_snapshot_names:  # Removed snapshots from source/VM dataset -> loose last flag
        bkp_ids = [b[3:] for b in deleted_last_snapshot_names if b.startswith('is-')]
        Backup.objects.filter(id__in=bkp_ids).update(last=False)


@catch_exception
def _vm_backup_update_snapshots(data, src_attr, dst_attr):
    """Update backup attribute according to update_snapshots list of objects, which have always a name (file_path)
    attribute and another attribute that needs to be updated in the backup object"""
    update_snapshots = data.get('update_snapshots', None)

    if update_snapshots:  # Archived backups or size changed
        # Create dict {bkp.id: src_attr} (src_attr can be new_name or written)
        bkp_attrs = {b['name'].split('@')[-1][3:]: b[src_attr] for b in update_snapshots if '@is-' in b['name']}

        for b in Backup.objects.only('id', dst_attr).filter(id__in=bkp_attrs.keys()):
            setattr(b, dst_attr, bkp_attrs[str(b.id)])
            b.save(update_fields=(dst_attr,))


@cq.task(name='api.vm.backup.tasks.vm_backup_list_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_backup_list_cb(result, task_id, vm_uuid=None, node_uuid=None, bkp_ids=None):
    """
    A callback function for DELETE api.vm.backup.views.vm_backup_list.
    """
    bkps = Backup.objects.select_related('vm', 'dc').filter(id__in=bkp_ids)
    _bkp = bkps[0]
    action = result['meta']['apiview']['method']
    json = result.pop('json', '')
    message = result.get('message', json)
    data = {}
    obj_id = vm_uuid or node_uuid
    success = False

    try:  # save json from esbackup
        data = _bkp.json.load(json)
    except Exception as e:
        logger.error('Could not parse json output from %s vm_backup_list(%s, %s). Error: %s', action, obj_id, bkps, e)
        result['detail'] = message or json
    else:
        success = data.get('success', False)
        try:
            result['detail'] = _vm_backup_cb_detail(data)
        except Exception as ex:
            logger.exception(ex)
            result['detail'] = json.replace('\n', '')

    if _bkp.type == Backup.DATASET:
        _vm_backup_update_snapshots(data, 'written', 'size')  # Update size of remaining backups
        _vm_backup_deleted_last_snapshot_names(data)  # Remove last flag from deleted snapshots

    if result['returncode'] == 0 and success:
        if action == 'DELETE':
            bkps.delete()
            _bkp.update_zpool_resources()
            result['message'] = 'Backups successfully deleted'

    else:
        # noinspection PyTypeChecker
        files = [i['name'] for i in data.get('files', [])]
        if files:
            deleted_bkps = bkps.filter(file_path__in=files)
            logger.warning('Only some backups were deleted in %s vm_backup_list(%s, %s): "%s"',
                           action, obj_id, bkps, deleted_bkps)
            deleted_bkps.delete()
            _bkp.update_zpool_resources()

        _vm_backup_list_cb_failed(result, task_id, bkps, action)
        msg = data.get('msg', message)
        logger.error('Found nonzero returncode in result from %s vm_backup_list(%s, %s). Error: %s',
                     action, obj_id, bkps, msg)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg))

    task_log_cb_success(result, task_id, obj=_bkp.vm or _bkp.node, **result['meta'])
    return result


# noinspection PyUnusedLocal,PyUnusedLocal,PyUnusedLocal
def _vm_backup_cb_alert(result, task_id, bkp_id=None, task_exception=None, **kwargs):
    """Alert function for failed backup creation"""
    action = result['meta']['apiview']['method']

    if action == 'POST':
        action_msg = 'created'
    elif action == 'DELETE':
        action_msg = 'deleted'
    else:
        return  # Alert only failed creation and deletion

    bkp = getattr(task_exception, 'bkp', None)
    if not bkp:
        bkp = Backup.objects.select_related('vm').get(id=bkp_id)

    vm = bkp.vm
    if vm:
        Zabbix.vm_send_alert(vm, 'Backup %s of server %s@disk-%s could not be %s.' % (
            bkp.name, vm.hostname, bkp.array_disk_id, action_msg))


@cq.task(name='api.vm.backup.tasks.vm_backup_cb', base=MgmtCallbackTask, bind=True)
@callback(error_fun=_vm_backup_cb_alert)
def vm_backup_cb(result, task_id, vm_uuid=None, node_uuid=None, bkp_id=None):
    """
    A callback function for api.vm.backup.views.vm_backup.
    """
    bkp = Backup.objects.select_related('vm', 'dc').get(id=bkp_id)
    action = result['meta']['apiview']['method']
    json = result.pop('json', '')
    message = result.get('message', json)
    data = {}
    obj_id = vm_uuid or node_uuid
    success = False

    try:  # save json from esbackup
        data = bkp.json.load(json)
    except Exception as e:
        logger.error('Could not parse json output from %s vm_backup(%s, %s). Error: %s', action, obj_id, bkp, e)
        result['detail'] = message or json
    else:
        success = data.get('success', False)
        try:
            result['detail'] = _vm_backup_cb_detail(data)
        except Exception as ex:
            logger.exception(ex)
            result['detail'] = json.replace('\n', '')

    msg = data.get('msg', message)

    if action == 'PUT':
        vm = Vm.objects.get(uuid=vm_uuid)
        obj = vm
    else:
        vm = None
        obj = bkp.vm or bkp.node

        if bkp.type == Backup.DATASET:
            if action == 'POST':
                _vm_backup_update_snapshots(data, 'new_name', 'file_path')  # Update file_path of archived backups
                _vm_backup_deleted_last_snapshot_names(data)  # Remove last flag from deleted snapshots

            elif action == 'DELETE':
                _vm_backup_update_snapshots(data, 'written', 'size')  # Update size of remaining backups
                _vm_backup_deleted_last_snapshot_names(data)  # Remove last flag from deleted snapshots

    if result['returncode'] == 0 and success:
        if action == 'POST':
            if bkp.type == Backup.DATASET:
                bkp.file_path = data.get('backup_snapshot', '')
                bkp.size = data.get('backup_snapshot_size', None)

                if data.get('last_snapshot_name', None):
                    bkp.last = True
            else:
                bkp.file_path = data.get('file', '')
                bkp.size = data.get('size', None)
                bkp.checksum = data.get('checksum', '')

            result['message'] = 'Backup successfully created'

            if bkp.fsfreeze:
                if 'freeze failed' in msg:
                    bkp.fsfreeze = False
                    result['message'] += ' (filesystem freeze failed)'
                    Zabbix.vm_send_alert(bkp.vm, 'Backup %s of server %s@disk-%s was created, but filesystem freeze '
                                                 'failed.' % (bkp.name, bkp.vm.hostname, bkp.array_disk_id),
                                         priority=Zabbix.zbx.WARNING)

            bkp.mainifest_path = data.get('metadata_file', '')
            bkp.time = data.get('time_elapsed', None)
            bkp.status = bkp.OK
            bkp.save()

            if bkp.define and bkp.define.retention:  # Retention - delete oldest snapshot
                assert bkp.vm == bkp.define.vm
                assert bkp.disk_id == bkp.define.disk_id
                from api.vm.backup.views import vm_backup_list
                _delete_oldest(Backup, bkp.define, vm_backup_list, 'bkpnames', task_id, LOG_BKPS_DELETE)

            bkp.update_zpool_resources()

        elif action == 'PUT':
            bkp.status = bkp.OK
            bkp.save_status()

            if result['meta']['apiview']['force']:  # Remove all snapshots
                disk = vm.json_active_get_disks()[result['meta']['apiview']['target_disk_id'] - 1]
                real_disk_id = Snapshot.get_real_disk_id(disk)
                # TODO: check indexes
                Snapshot.objects.filter(vm=vm, disk_id=real_disk_id).delete()

            vm.revert_notready()
            result['message'] = 'Backup successfully restored'

        elif action == 'DELETE':
            bkp.delete()
            bkp.update_zpool_resources()
            result['message'] = 'Backup successfully deleted'

    else:
        _vm_backup_cb_failed(result, task_id, bkp, action, vm=vm)  # Delete backup or update backup status
        logger.error('Found nonzero returncode in result from %s vm_backup(%s, %s). Error: %s',
                     action, obj_id, bkp, msg)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg), bkp=bkp)

    task_log_cb_success(result, task_id, obj=obj, **result['meta'])
    return result


@cq.task(name='api.vm.backup.tasks.vm_backup_beat')
def vm_backup_beat(bkp_define_id):
    """
    This is a periodic beat task. Run POST vm_backup according to backup definition.
    """
    from api.vm.backup.views import vm_backup

    bkp_define = BackupDefine.objects.get(id=bkp_define_id)
    vm = bkp_define.vm
    disk_id = bkp_define.array_disk_id
    defname = bkp_define.name
    request = get_dummy_request(vm.dc, method='POST', system_user=True)
    request.define_id = bkp_define.id  # Automatic task
    # Go!
    res = call_api_view(request, 'POST', vm_backup, vm.hostname, defname, data={'disk_id': disk_id,
                                                                                'fsfreeze': bkp_define.fsfreeze})

    if res.status_code == 201:
        logger.info('POST vm_backup(%s, %s, {disk_id=%s}) was successful: %s', vm, defname, disk_id, res.data)
    else:
        # Need to log this, because nobody else does (+ there is no PENDING task)
        detail = 'hostname=%s, bkpname=%s, disk_id=%s, Error: %s' % (vm.hostname, bkp_define.generate_backup_name(),
                                                                     disk_id, get_task_error_message(res.data))
        task_log_error(task_id_from_task_id(vm_backup_beat.request.id, dc_id=vm.dc.id),
                       LOG_BKP_CREATE, vm=vm, detail=detail, update_user_tasks=False)

        if res.status_code == HTTP_423_LOCKED:
            logger.warning('Running POST vm_backup(%s, %s, {disk_id=%s}) failed: %s (%s): %s',
                           vm, defname, disk_id, res.status_code, res.status_text, res.data)
        else:
            logger.error('Running POST vm_backup(%s, %s, {disk_id=%s}) failed: %s (%s): %s',
                         vm, defname, disk_id, res.status_code, res.status_text, res.data)
            Zabbix.vm_send_alert(vm, 'Automatic backup %s/disk-%s@%s failed to start.' %
                                 (vm.hostname, disk_id, defname))
