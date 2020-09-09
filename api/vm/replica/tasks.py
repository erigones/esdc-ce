import json
import base64
from datetime import datetime

from django.db.models import Q
from django.dispatch import receiver
from pytz import utc

try:
    # noinspection PyPep8Naming
    import cPickle as pickle
except ImportError:
    import pickle

from core.celery.config import ERIGONES_TASK_USER
from que.tasks import cq, get_task_logger, execute
from que.mgmt import MgmtCallbackTask
from que.utils import task_id_from_string, delete_task
from que.internal import InternalTask
from que.exceptions import TaskException
from api.utils.request import get_dummy_request
from api.utils.views import call_api_view
from api.task.utils import callback
from api.task.tasks import task_log_cb_success
from api.task.response import to_string
from api.task.signals import task_cleanup_signal
from api.vm.messages import LOG_STOP_FORCE
from api.vm.status.views import vm_status
from api.vm.status.tasks import vm_status_one
from api.vm.snapshot.views import vm_snapshot_list
from api.vm.replica.events import VmReplicaSynced
from vms.utils import ConcatJSONDecoder
from vms.models import Vm, SlaveVm, Backup
from vms.signals import vm_json_active_changed, vm_node_changed

__all__ = ('vm_replica_cb',)

logger = get_task_logger(__name__)

REPLICA_LOG_DETAIL = frozenset(['msg', 'rc', 'time_elapsed'])
REPLICA_SERVICE_STATES = {
    'absent': SlaveVm.DIS,
    'offline': SlaveVm.OFF,
    'online': SlaveVm.ON,
}


def _vm_replica_cb_detail(repname, action, jsons, key_json_idx=None):
    """Create tasklog detail"""
    res = {'repname': repname}

    if not jsons:
        return res

    for out in jsons:
        if 'msg' in out:
            res['msg'] = out['msg']
            res['rc'] = out['rc']

    if key_json_idx is None:
        if action == 'POST':
            key_json_idx = 0
        elif action == 'DELETE':
            key_json_idx = -1

    if key_json_idx is not None:
        try:
            res['time_elapsed'] = jsons[key_json_idx]['time_elapsed']
        except (IndexError, KeyError):
            pass

    return ', '.join(['%s=%s' % (k, to_string(v)) for k, v in res.items()])


def _load_jsons(string):
    """Parse multiple json objects"""
    if not string:
        raise ValueError('Empty json string')
    return json.loads(string, cls=ConcatJSONDecoder)


def _save_svc_state(slave_vm, jsons):
    """Get last service state from jsons and save it to slave VM"""
    service_state = None

    for out in jsons:
        if 'service_state' in out:
            service_state = REPLICA_SERVICE_STATES.get(out['service_state'], SlaveVm.OFF)

    if service_state is not None:
        slave_vm.sync_status = service_state

    return service_state


def _save_svc_params(slave_vm, jsons):
    """Get service params from esrep output and save it to slave VM"""
    last_json = jsons[-1]

    for opt in ('sleep_time', 'bwlimit'):
        if opt in last_json:
            setattr(slave_vm, 'rep_' + opt, last_json[opt])


def _parse_vm_replica_result(result, vm, slave_vm, action, key_json_idx=None, cb_name='vm_replica'):
    """vm_replica task result parser"""
    jsons = result.pop('jsons', '')

    try:
        parsed_jsons = _load_jsons(jsons)
    except Exception as exc:
        parsed_jsons = []
        logger.error('Could not parse json output from %s %s(%s, %s). Error: %s',
                     action, cb_name, vm.uuid, slave_vm.uuid, exc)
        result['detail'] = result.get('message', '') or jsons
    else:
        result['detail'] = _vm_replica_cb_detail(slave_vm.name, action, parsed_jsons, key_json_idx=key_json_idx)

    return result, parsed_jsons


def _parse_last_sync(response):
    """Return last sync datetime object"""
    return datetime.utcfromtimestamp(int(response['timestamp'])).replace(tzinfo=utc)


def _update_task_result_success(result, slave_vm, action, msg):
    """Update task result => unified api call output"""
    result['message'] = msg
    result['hostname'] = slave_vm.master_vm.hostname
    result['repname'] = slave_vm.name

    if action == 'DELETE':
        result['last_sync'] = result['enabled'] = None
    else:
        result.update(slave_vm.web_data)

        last_sync = slave_vm.last_sync
        if last_sync:
            last_sync = last_sync.astimezone(utc).isoformat()
            if last_sync.endswith('+00:00'):
                last_sync = last_sync[:-6] + 'Z'

        result['last_sync'] = last_sync
        result['enabled'] = slave_vm.rep_enabled

    return result


def _update_task_result_failure(result, detail):
    """Update task result => unified api call output. Return message for TaskException"""
    msg = 'Got bad return code (%s)' % result['returncode']
    result['message'] = msg

    return '%s. Error: %s' % (msg, detail)


def _delete_tasks(vm, tasks):
    """Delete tasks for a VM"""
    for tid in tasks:
        logger.info('Deleting VM %s task %s', vm, tid)
        try:
            ok, err = delete_task(tid)
        except Exception as exc:
            logger.exception(exc)
        else:
            if ok:
                logger.warn('Successfully delete task %s', ok)
            else:
                logger.warn('Could not delete task %s: %s', tid, err)


def _vm_shutdown(vm):
    """Create internal shutdown task"""
    cmd = 'vmadm stop -F ' + vm.uuid
    lock = 'vmadm stop ' + vm.uuid
    meta = {
        'replace_text': ((vm.uuid, vm.hostname),),
        'msg': LOG_STOP_FORCE, 'vm_uuid': vm.uuid
    }

    tid, err = execute(ERIGONES_TASK_USER, None, cmd, meta=meta, lock=lock, callback=False, expires=None,
                       queue=vm.node.fast_queue, nolog=True, ping_worker=False, check_user_tasks=False)

    if err:
        logger.error('Failed (%s) to create internal shutdown task for old master VM %s', err, vm)
    else:
        logger.info('Created internal shutdown task %s for old master VM %s', tid, vm)

    return tid, err


# noinspection PyUnusedLocal
def _vm_replica_cb_failed(result, task_id, vm, slave_vm, action):
    """Callback helper for failed vm_replica task (called only by emergency cleanup)"""
    if action == 'POST':
        vm.revert_notready()
        slave_vm.delete()


# noinspection PyUnusedLocal
@receiver(task_cleanup_signal)
def vm_replica_cb_failed_cleanup(sender, apiview, result, task_id, status, obj, **kwargs):
    """Signal receiver emitted after task is revoked."""
    if sender == 'vm_replica':
        slave_vm = SlaveVm.get_by_uuid(apiview['slave_vm_uuid'])
        _vm_replica_cb_failed(result, task_id, obj, slave_vm, apiview['method'])


# noinspection PyUnusedLocal
def _vm_replica_failover_cb_failed(result, task_id, vm):
    """Callback helper for failed vm_replica_failover task (called only by emergency cleanup)"""
    vm.revert_notready()


# noinspection PyUnusedLocal
@receiver(task_cleanup_signal)
def vm_replica_failover_cb_failed_cleanup(sender, apiview, result, task_id, status, obj, **kwargs):
    """Signal receiver emitted after task is revoked."""
    if sender == 'vm_replica_failover':
        _vm_replica_failover_cb_failed(result, task_id, obj)


@cq.task(name='api.vm.replica.tasks.vm_replica_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_replica_cb(result, task_id, vm_uuid=None, slave_vm_uuid=None):
    """
    A callback function for api.vm.replica.views.vm_replica.
    """
    slave_vm = SlaveVm.get_by_uuid(slave_vm_uuid)
    vm = slave_vm.master_vm
    assert vm.uuid == vm_uuid
    action = result['meta']['apiview']['method']
    result, jsons = _parse_vm_replica_result(result, vm, slave_vm, action)

    if action == 'POST':
        vm.revert_notready()

        if jsons and jsons[0].get('success', False):
            esrep_init = jsons[0]
            # New slave VM was successfully created on target node
            # noinspection PyTypeChecker
            json_active = pickle.loads(base64.b64decode(esrep_init.pop('slave_json')))
            slave_vm.vm.json = slave_vm.vm.json_active = json_active
            slave_vm.vm.status = Vm.STOPPED
            slave_vm.vm.save(update_fields=('status', 'status_change', 'enc_json', 'enc_json_active', 'changed'))
            slave_vm.last_sync = _parse_last_sync(esrep_init)
        else:
            slave_vm.delete()

    sync_status = _save_svc_state(slave_vm, jsons)
    msg = result['detail']

    if result['returncode'] == 0 and jsons:
        if action == 'POST':
            _save_svc_params(slave_vm, jsons)
            slave_vm.save()
            msg = 'Server replica was successfully initialized'
        elif action == 'PUT':
            _save_svc_params(slave_vm, jsons)
            slave_vm.save()
            msg = 'Server replication service was successfully updated'
        elif action == 'DELETE':
            slave_vm.delete()
            msg = 'Server replica was successfully destroyed'

            # noinspection PyTypeChecker
            if len(jsons[-1]['master_cleaned_disks']) != len(vm.json_active_get_disks()):
                warning = "WARNING: Master server's disks were not cleaned properly"
                result['detail'] += ' msg=' + warning
                msg += '; ' + warning
    else:
        if sync_status is not None:
            slave_vm.save(update_fields=('sync_status',))
        logger.error('Found nonzero returncode in result from %s vm_replica(%s, %s). Error: %s',
                     action, vm_uuid, slave_vm_uuid, msg)
        errmsg = _update_task_result_failure(result, msg)
        raise TaskException(result, errmsg)

    _update_task_result_success(result, slave_vm, action, msg)
    task_log_cb_success(result, task_id, vm=vm, **result['meta'])
    return result


@cq.task(name='api.vm.replica.tasks.vm_replica_failover_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_replica_failover_cb(result, task_id, vm_uuid=None, slave_vm_uuid=None):
    """
    A callback function for api.vm.replica.views.vm_replica_failover.
    """
    slave_vm = SlaveVm.get_by_uuid(slave_vm_uuid, sr=('vm', 'master_vm', 'vm__node', 'vm__dc',))
    vm = slave_vm.master_vm
    assert vm.uuid == vm_uuid
    action = result['meta']['apiview']['method']
    force = result['meta']['apiview']['force']
    result, jsons = _parse_vm_replica_result(result, vm, slave_vm, action, key_json_idx=-1,
                                             cb_name='vm_replica_failover')
    sync_status = _save_svc_state(slave_vm, jsons)

    if result['returncode'] != 0:
        if sync_status is not None:
            slave_vm.save(update_fields=('sync_status',))

        vm.revert_notready()
        msg = result['detail']
        logger.error('Found nonzero returncode in result from %s vm_replica_failover(%s, %s). Error: %s',
                     action, vm_uuid, slave_vm_uuid, msg)
        errmsg = _update_task_result_failure(result, msg)
        raise TaskException(result, errmsg)

    # New master VM was born
    # Delete tasks for old master
    if force:
        tasks = list(vm.tasks.keys())
        try:
            tasks.remove(task_id)
        except ValueError:
            pass
        _delete_tasks(vm, tasks)

    # Create internal shutdown task of old master VM
    old_vm_status = result['meta']['apiview']['orig_status']
    _vm_shutdown(vm)

    # Save new master, degrade old master
    slave_vm.master_vm.revert_notready(save=False)
    new_vm = slave_vm.fail_over()

    # Re-check status of old master (current degraded slave) because it was shut down,
    # but the state wasn't save (it was notready back then)
    vm_status_one(task_id, vm)

    # Continue with prompting of new master and degradation of old
    SlaveVm.switch_vm_snapshots_node_storages(new_vm, nss=vm.get_node_storages())
    # Force update of zabbix
    vm_json_active_changed.send(task_id, vm=new_vm, old_json_active={}, force_update=True)  # Signal!

    if new_vm.node != vm.node:
        vm_node_changed.send(task_id, vm=new_vm, force_update=True)  # Signal!

    msg = 'Server replica was successfully promoted to master'
    _update_task_result_success(result, slave_vm, action, msg)
    task_log_cb_success(result, task_id, vm=new_vm, **result['meta'])
    request = get_dummy_request(vm.dc, method='PUT', system_user=True)

    # Mark pending backups as "lost" :(  TODO: implement vm_backup_sync
    new_vm.backup_set.filter(status=Backup.PENDING).update(status=Backup.LOST)

    # Sync snapshots on new master VM (mark missing snapshots as "lost")
    for disk_id, _ in enumerate(new_vm.json_active_get_disks(), start=1):
        call_api_view(request, 'PUT', vm_snapshot_list, new_vm.hostname, data={'disk_id': disk_id}, log_response=True)

    if old_vm_status == Vm.RUNNING:
        # Start new master VM
        call_api_view(request, 'PUT', vm_status, new_vm.hostname, action='start', log_response=True)

    return result


@cq.task(name='api.vm.replica.tasks.vm_replica_reinit_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_replica_reinit_cb(result, task_id, vm_uuid=None, slave_vm_uuid=None):
    """
    A callback function for api.vm.replica.views.vm_replica_reinit.
    """
    slave_vm = SlaveVm.get_by_uuid(slave_vm_uuid)
    vm = slave_vm.master_vm
    assert vm.uuid == vm_uuid
    action = result['meta']['apiview']['method']
    result, jsons = _parse_vm_replica_result(result, vm, slave_vm, action, key_json_idx=0, cb_name='vm_replica_reinit')

    if result['returncode'] != 0:
        if jsons and jsons[0].get('success', False):  # Successfully reversed replication
            slave_vm.last_sync = _parse_last_sync(jsons[0])
            slave_vm.rep_reinit_required = False
            slave_vm.save()

        msg = result['detail']
        logger.error('Found nonzero returncode in result from %s vm_replica_reinit(%s, %s). Error: %s',
                     action, vm_uuid, slave_vm_uuid, msg)
        errmsg = _update_task_result_failure(result, msg)
        raise TaskException(result, errmsg)

    slave_vm.rep_reinit_required = False
    slave_vm.last_sync = _parse_last_sync(jsons[0])
    _save_svc_state(slave_vm, jsons)
    _save_svc_params(slave_vm, jsons)
    slave_vm.save()
    msg = 'Server replica was successfully reinitialized'
    _update_task_result_success(result, slave_vm, action, msg)
    task_log_cb_success(result, task_id, vm=vm, **result['meta'])

    return result


# noinspection PyUnusedLocal
@cq.task(name='api.vm.replica.tasks.vm_replica_sync_cb', base=InternalTask)
def vm_replica_sync_cb(result, task_id):
    """
    Internal task called as callback by esrep after each sync.
    After successful update of slave_vm.last_sync it will create an event and send it into socket.io.
    """
    slave_vm = result['slave']
    master_vm_hostname = result['master_hostname']
    last_sync = _parse_last_sync(result)
    slave_vm_filter = Q(vm=slave_vm) & (Q(last_sync__lt=last_sync) | Q(last_sync__isnull=True))

    if SlaveVm.objects.filter(slave_vm_filter).update(last_sync=last_sync):
        logger.debug('Slave VM %s (%s) last_sync=%s saved', slave_vm, master_vm_hostname, last_sync)
        event_task_id = task_id_from_string(None, task_prefix=result['task_prefix'])
        VmReplicaSynced(event_task_id, vm_hostname=master_vm_hostname, last_sync=last_sync.isoformat()).send()
    else:
        logger.warn('Slave VM %s (%s) received invalid last_sync=%s', slave_vm, master_vm_hostname, last_sync)

    return result
