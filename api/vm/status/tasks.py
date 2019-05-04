from math import log10
from datetime import datetime

from pytz import utc
from dateutil.parser import parse as datetime_parse
# noinspection PyProtectedMember
from django.core.cache import cache, caches
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from celery import states

from que.tasks import cq, execute, get_task_logger
from que.mgmt import MgmtCallbackTask
from que.utils import task_id_from_task_id
from que.internal import InternalTask
from que.exceptions import TaskException
# noinspection PyProtectedMember
from api.task.tasks import task_log_cb_success
from api.task.utils import task_log, callback, mgmt_lock
from api.vm.base.utils import is_vm_missing, vm_deploy, vm_update_ipaddress_usage, vm_delete_snapshots_of_removed_disks
from api.vm.messages import LOG_STATUS_CHANGE
from api.vm.status.events import VmStatusChanged
from vms.models import Vm, Node
from vms.signals import (vm_running, vm_stopped, vm_json_active_changed,
                         vm_status_changed as vm_status_changed_sig)

__all__ = (
    'vm_status_all_cb',
    'vm_status_event_cb',
    'vm_status_current_cb',
    'vm_status_cb',
    'vm_uptime_all',
)
# + There is a vm_status_changed function, which can be used as a callback by other tasks
# + And a vm_status_all function, which is called when compute node gets online or after mgmt worker starts
# + And a vm_status_one function, which is called in case we need to check one's VM status

logger = get_task_logger(__name__)

redis = caches['redis'].master_client

KEY_PREFIX = '%s:%s:' % (cache.key_prefix, cache.version)
ERIGONES_TASK_USER = cq.conf.ERIGONES_TASK_USER


def _get_task_time(result, key='finish_time'):
    """
    Fetch and parse exec_time or finish_time from execute task.
    """
    task_time = result['meta'].get(key, None)

    if task_time:
        return datetime_parse(task_time).replace(tzinfo=utc)
    else:
        return None


def _parse_timestamp(exit_or_boot_timestamp):
    """
    Parse boot_timestamp or exit_timestamp and return datetime object or None.
    """
    timestamp = exit_or_boot_timestamp.strip(':')

    if timestamp:
        return datetime_parse(timestamp).replace(tzinfo=utc)
    else:
        return None


# noinspection PyUnusedLocal
def vm_status_all(task_id, node, **kwargs):
    """
    This function runs a vmadm list command on a compute node for all VMs
    Called by node_online signal or node_sysinfo_cb or node_worker_status_check_all after mgmt worker starts.
    The consequent callback parses the output and may change VM's status in DB.
    """
    if not node.is_compute:
        logger.info('Skipping vm_status_all for non-compute node %s', node)
        return

    logger.info('Running vm_status_all on compute node %s by %s', node, task_id)
    tid, err = execute(ERIGONES_TASK_USER, None, 'vmadm list -p -H -o uuid,state,exit_timestamp,boot_timestamp',
                       callback=('api.vm.status.tasks.vm_status_all_cb', {'node_uuid': node.uuid}),
                       queue=node.fast_queue, nolog=True, ping_worker=False, check_user_tasks=False)

    if err:
        logger.error('Got error (%s) when running task execute[%s]("vmadm list -p -H -o uuid,state") on %s',
                     err, tid, node.hostname)
    else:
        logger.info('Created vm_status_all task %s by %s', tid, task_id)

    return tid


# noinspection PyUnusedLocal
def vm_status_one(task_id, vm):
    """
    This function runs a vmadm list command on a compute node for a VM.
    Called by api.vm.base.tasks.vm_create_cb in case of an ERROR.
    The consequent callback parses the output and may change VM's status in DB.
    """
    logger.info('Running vm_status_one for VM %s by %s', vm, task_id)
    node = vm.node
    tid, err = execute(ERIGONES_TASK_USER, None,
                       'vmadm list -p -H -o uuid,state,exit_timestamp,boot_timestamp uuid=' + vm.uuid,
                       callback=('api.vm.status.tasks.vm_status_all_cb', {'node_uuid': node.uuid}),
                       queue=node.fast_queue, nolog=True, ping_worker=False, check_user_tasks=False)

    if err:
        logger.error('Got error (%s) when running task execute[%s]("vmadm list -p -H -o uuid,state") on %s',
                     err, tid, node.hostname)
    else:
        logger.info('Created vm_status_one task %s by %s', tid, task_id)

    return tid


def vm_status_changed(tid, vm, state, old_state=None, save_state=True, deploy_over=False, change_time=None):
    """
    This function is something like a dummy callback.
    It should be called when VM state is changed from a task.
    """
    if change_time:
        old_change_time = cache.get(Vm.status_change_key(vm.uuid))

        if old_change_time and old_change_time > change_time:
            logger.warn('Ignoring status change %s->%s of VM %s (%s) because it is too old: %s > %s',
                        vm.status, state, vm, vm.uuid, old_change_time, change_time)
            return None

    # save to DB and also update cache
    if save_state:
        vm.status = state

        if state != Vm.STOPPING:  # Update VM uptime when VM status changes to stopped or running
            # update VM uptime
            uptime_msg = vm.update_uptime()  # not running save() -> saved below

            if uptime_msg:
                logger.info('Uptime message: %s', uptime_msg)

        if old_state is not None:  # if cached status != vm.status (don't remember why we need this)
            vm._orig_status = old_state

        vm.save(update_fields=('status', 'status_change', 'uptime', 'uptime_changed'), status_change_time=change_time)

    if deploy_over:  # deploy process ended
        # Set the deploy_finished flag to inform vm_create_cb
        vm.set_deploy_finished()

    if vm.is_slave_vm():
        logger.info('Detected status change of slave VM %s - "%s"', vm.uuid, vm)
        return None

    # Adjust task ID according to VM parameters
    tid = task_id_from_task_id(tid, owner_id=vm.owner.id, dc_id=vm.dc_id)

    # Signals!
    vm_status_changed_sig.send(tid, vm=vm, old_state=old_state, new_state=state)  # Signal!
    if vm.status == vm.RUNNING:
        vm_running.send(tid, vm=vm, old_state=old_state)  # Signal!
    elif vm.status == vm.STOPPED:
        vm_stopped.send(tid, vm=vm, old_state=old_state)  # Signal!

    # data for next operations
    msg = LOG_STATUS_CHANGE
    task_event = VmStatusChanged(tid, vm)

    # log task
    task_log(tid, msg, vm=vm, owner=vm.owner, task_result=task_event.result,
             task_status=states.SUCCESS, time=vm.status_change, update_user_tasks=False)

    # inform users (VM owners logged in GUI)
    task_event.send()


def _save_vm_status(task_id, vm, new_state, old_state=None, **kwargs):
    """Helper function used by _vm_status_check() and vm_status_cb() in order to save new VM status"""
    if old_state is None:  # Called from vm_status_cb() -> we need to force state change no matter what
        logger.warn('Detected status change %s->%s from vm_status(%s)', vm.status, new_state, vm.uuid)
        old_state = vm.status

    # Hurrah!
    vm_status_changed(task_id, vm, new_state, old_state=old_state, **kwargs)  # calls save()


@mgmt_lock(timeout=300, key_args=(2,), wait_for_release=True, base_name='vm_status_changed')  # noqa: R701
def _vm_status_check(task_id, node_uuid, uuid, state, state_cache=None, vm=None,  # noqa: R701
                     change_time=None, force_change=False, **kwargs):
    """Helper function for checking VM's new/actual state used by following callbacks:
        - vm_status_all_cb
        - vm_status_event_cb
        - vm_status_current_cb
    """
    if state_cache is None:
        try:  # vm state not in cache, loading from DB...
            vm = Vm.objects.select_related('slavevm').get(uuid=uuid)
        except Vm.DoesNotExist:
            logger.warn('Got status of undefined vm (%s) - ignoring', uuid)
            return
        else:  # ...and saving to cache
            state_cache = vm.status
            cache.set(Vm.status_key(uuid), vm.status)
    else:
        state_cache = int(state_cache)

    if state_cache == state:
        logger.info('Ignoring new status %s of vm %s because it is already saved', state, uuid)
        return

    # vm status changed!!!
    # Deploying stuff
    deploy = False
    deploy_finish = False
    deploy_over = False
    deploy_dummy = False

    if force_change:
        logger.warn('Detected FORCED status change for vm %s', uuid)

    elif state_cache == Vm.CREATING:
        if state == Vm.RUNNING:
            logger.warn('Detected new status %s for vm %s. We were waiting for this. '
                        'Switching state to (A) "running (2)" or (B) "deploying_start (12)" or '
                        '(C) "deploying_dummy (14)" and running vm_deploy(force_stop=True).', state, uuid)
            deploy = True
        else:
            logger.warn('Detected new status %s for vm %s, but vm waiting for deploy (%s). '
                        'Awaiting running state.', state, uuid, state_cache)
            return

    elif state_cache == Vm.DEPLOYING_DUMMY:
        if state == Vm.STOPPED:
            logger.warn('Detected new status %s for vm %s. We were waiting for this. Dummy deploy is finished. '
                        'Switching state to "stopped".', state, uuid)
            deploy_over = True
        else:
            logger.warn('Detected new status %s for vm %s, but vm is dummy deploying (%s). '
                        'Awaiting stopped state.', state, uuid, state_cache)
            return

    elif state_cache == Vm.DEPLOYING_START:
        if state == Vm.STOPPED:
            logger.warn('Detected new status %s for vm %s. We were waiting for this. '
                        'Switching state to "deploying_finish (13)" and running vm_deploy task.', state, uuid)
            deploy_finish = True
        else:
            logger.warn('Detected new status %s for vm %s, but vm is deploying (%s). '
                        'Awaiting stopped state.', state, uuid, state_cache)
            return

    elif state_cache == Vm.DEPLOYING_FINISH:
        if state == Vm.RUNNING:
            logger.warn('Detected new status %s for vm %s. We were waiting for this. Deploy is finished. '
                        'Switching state to "running".', state, uuid)
            deploy_over = True
        else:
            logger.warn('Detected new status %s for vm %s, but vm waiting for finishing deploy (%s). '
                        'Awaiting running state.', state, uuid, state_cache)
            return

    elif state_cache not in Vm.STATUS_KNOWN:
        logger.debug('Detected unknown cached status %s for vm %s', state_cache, uuid)
        return

    # HERE WE GO
    logger.warn('Detected status change %s->%s for vm %s', state_cache, state, uuid)

    try:  # get VM
        if not vm:
            vm = Vm.objects.select_related('node', 'slavevm').get(uuid=uuid)
    except Vm.DoesNotExist:
        logger.error('Status of undefined vm (%s) changed', uuid)
        return

    if vm.node.uuid != node_uuid:  # double vm protection
        logger.error('Detected status change for vm %s on node %s, but the vm should be on %s!',
                     uuid, vm.node.uuid, node_uuid)
        return

    if deploy:  # deploy process started (VM is running)
        if vm.is_deploy_needed():
            vm.status = Vm.DEPLOYING_START
            vm.save_status(status_change_time=change_time)
            return  # The deploy will be over after VM is stopped by itself from inside
        elif vm.is_blank():  # Empty VM is running -> stop VM via vm_deploy()
            vm.status = Vm.DEPLOYING_DUMMY
            vm.save_status(status_change_time=change_time)
            deploy_dummy = True  # The deploy will be over after VM is stopped by vm_deploy()
        else:  # Deploy is not needed, but VM has an image. We are done here -> VM is running
            deploy_over = True

    if deploy_finish:  # finish deploy process -> the deploy will be over when VM is started by vm_deploy()
        vm.status = Vm.DEPLOYING_FINISH
        vm.save_status(status_change_time=change_time)

    if deploy_finish or deploy_dummy:
        _tid, _err = vm_deploy(vm, force_stop=deploy_dummy)

        if _err:
            logger.error('Got error when creating deploy task. Task: %s. Error: %s.', _tid, _err)
        else:
            logger.warn('Created deploy task: %s.', _tid)

        return

    if vm.is_changing_status():
        logger.warn('Detected running vm_status task (pending state) for vm %s', uuid)

    _save_vm_status(task_id, vm, state, old_state=state_cache, deploy_over=deploy_over, change_time=change_time,
                    **kwargs)

    return state


# noinspection PyUnusedLocal
@cq.task(name='api.vm.status.tasks.vm_status_all_cb', ignore_result=True)
def vm_status_all_cb(result, task_id, node_uuid=None):
    """
    A callback function for api.vm.status.tasks.vm_status_all.
    Compare actual VM status against cached data. If something changes emit a message and update DB.
    """
    tid = vm_status_all_cb.request.id

    if result.get('returncode') != 0:
        logger.warn('Found nonzero returncode for task %s(%s)', 'vm_status_all', node_uuid)
        return

    vms = []
    r_states = redis.pipeline()

    # The result['stdout'] contains output from `vmadm list -o uuid,state,exit_timestamp,boot_timestamp`
    # Only one property of exit_timestamp and boot_timestamp will be in the command output
    for line in result['stdout'].splitlines():
        i = line.strip().split(':', 2)  # uuid:state:exit_timestamp,boot_timestamp

        if len(i) != 3:
            logger.error('Could not parse line ("%s") from output of task %s(%s)',
                         line, 'vm_status_all', node_uuid)
            continue

        if i[1] in Vm.STATUS_UNUSED:  # 255
            logger.info('Ignoring unusable status ("%s") from output of task %s(%s)',
                        line, 'vm_status_all', node_uuid)
            continue

        if i[1] not in Vm.STATUS_DICT:
            logger.error('Unknown status in vmadm list output ("%s") from output of task %s(%s)',
                         line, 'vm_status_all', node_uuid)
            continue

        uuid = i[0]
        state = Vm.STATUS_DICT[i[1]]  # returns int
        exit_or_boot_timestamp = i[2]
        # Save vm status line into vms list for later status check because we need to pair it to the redis result list
        vms.append((uuid, state, exit_or_boot_timestamp))
        r_states.get(KEY_PREFIX + Vm.status_key(uuid))

    if not vms:
        return

    vm_states = r_states.execute()

    for i, line in enumerate(vms):
        uuid, state, exit_or_boot_timestamp = line
        state_cache = vm_states[i]  # None or string
        # Check and eventually save VM's status
        _vm_status_check(tid, node_uuid, uuid, state, state_cache=state_cache,
                         change_time=_parse_timestamp(exit_or_boot_timestamp))


@cq.task(name='api.vm.status.tasks.vm_status_event_cb', base=InternalTask, ignore_result=True)
def vm_status_event_cb(result, task_id):
    """
    Callback task run by erigonesd-vmon service after detecting a VM status change.
    """
    vm_uuid = result['zonename']
    state_cache = cache.get(Vm.status_key(vm_uuid))
    state = Vm.STATUS_DICT[result['state']]
    when = result['when']
    change_time = datetime.utcfromtimestamp(float(when) / pow(10, int(log10(when)) - 9)).replace(tzinfo=utc)
    # Check and eventually save VM's status
    _vm_status_check(task_id, result['node_uuid'], vm_uuid, state, state_cache=state_cache, change_time=change_time)


@cq.task(name='api.vm.status.tasks.vm_status_current_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_status_current_cb(result, task_id, vm_uuid=None, force_change=False):
    """
    A callback function for GET api.vm.status.views.vm_status.
    It is responsible for displaying the actual VM status to the user and optionally changing status in DB.
    """
    stdout = result.pop('stdout', '')
    stderr = result.pop('stderr', '')
    rc = result.pop('returncode')

    if rc != 0:
        logger.error('Found nonzero returncode in result from GET vm_status(%s). Error: %s', vm_uuid, stderr)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (rc, stderr))

    line = stdout.strip().split(':')
    result['status'] = line[0]
    result['status_changed'] = False
    vm = Vm.objects.select_related('node', 'slavevm').get(uuid=vm_uuid)

    try:
        if result['status']:
            state = Vm.STATUS_DICT[result['status']]
        else:
            # vmadm list returned with rc=0 and empty stdout => VM does not exist on compute node
            state = Vm.NOTCREATED
            result['status'] = dict(Vm.STATUS).get(state)
    except (KeyError, IndexError):
        result['message'] = 'Unidentified VM status'
    else:
        result['message'] = ''
        state_cache = cache.get(Vm.status_key(vm_uuid))
        # Check and eventually save VM's status
        if _vm_status_check(task_id, vm.node.uuid, vm_uuid, state, state_cache=state_cache, force_change=force_change,
                            change_time=_get_task_time(result, 'exec_time')):
            result['status_changed'] = True

    vm.tasks_del(task_id)
    return result


def _vm_status_cb_failed(result, task_id, vm):
    """
    After failed PUT vm_status() it may be required to re-check the current VM's status.
    """
    if vm.status == Vm.STOPPING:
        # This is a special case because the "vmadm stop" command has failed, but we have manually changed the
        # VM status to stopping in PUT vm_status() and there is nothing which would change the status back.
        # So lets restore the last known status and double-check via vm_status_one()
        vm.save_status(result['meta']['last_status'])

    vm_status_one(task_id, vm)


@cq.task(name='api.vm.status.tasks.vm_status_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_status_cb(result, task_id, vm_uuid=None):
    """
    A callback function for PUT api.vm.status.views.vm_status.
    Always updates the VM's status in DB.
    """
    vm = Vm.objects.select_related('slavevm').get(uuid=vm_uuid)
    msg = result.get('message', '')
    json = result.pop('json', None)

    if result['returncode'] == 0 and msg and msg.find('Successfully') == 0:
        # json was updated
        if result['meta']['apiview']['update'] and msg.find('Successfully updated') != -1:
            old_json_active = vm.json_active

            try:  # save json from smartos
                json_active = vm.json.load(json)
                vm_delete_snapshots_of_removed_disks(vm)  # Do this before updating json and json_active
                vm.json_active = json_active
                vm.json = json_active
            except Exception as e:
                logger.exception(e)
                logger.error('Could not parse json output from vm_status(%s). Error: %s', vm_uuid, e)
            else:
                with transaction.atomic():
                    vm.save(update_node_resources=True, update_storage_resources=True,
                            update_fields=('enc_json', 'enc_json_active', 'changed'))
                    vm_update_ipaddress_usage(vm)
                    vm_json_active_changed.send(task_id, vm=vm, old_json_active=old_json_active)  # Signal!

        change_time = _get_task_time(result, 'exec_time')

        if msg.find('Successfully started') >= 0:
            new_status = Vm.RUNNING
        elif msg.find('Successfully completed stop') >= 0:
            if result['meta']['apiview']['freeze']:
                new_status = Vm.FROZEN
                change_time = _get_task_time(result, 'finish_time')  # Force status save
            else:
                new_status = Vm.STOPPED
        elif msg.find('Successfully completed reboot') >= 0:
            new_status = Vm.RUNNING
        else:
            logger.error('Did not find successful status change in result from vm_status(%s). Error: %s', vm_uuid, msg)
            raise TaskException(result, 'Unknown status (%s)' % msg)

    else:
        logger.error('Found nonzero returncode in result from vm_status(%s). Error: %s', vm_uuid, msg)

        if is_vm_missing(vm, msg):
            logger.critical('VM %s has vanished from compute node!', vm_uuid)

            if vm.status == Vm.STOPPING:
                _save_vm_status(task_id, vm, Vm.STOPPED, change_time=_get_task_time(result, 'finish_time'))
        else:
            _vm_status_cb_failed(result, task_id, vm)

        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg))

    _save_vm_status(task_id, vm, new_status, change_time=change_time)
    task_log_cb_success(result, task_id, vm=vm, **result['meta'])

    return result


@cq.task(name='api.vm.status.tasks.vm_uptime_all')
def vm_uptime_all():
    """
    This is a periodic beat task. Update uptime for every running VM.
    """
    now = int(timezone.now().strftime('%s'))
    Vm.objects.filter(node__status=Node.ONLINE, status=Vm.RUNNING, uptime_changed__gt=0).update(
        uptime_changed=now, uptime=(F('uptime') + (now - F('uptime_changed'))))
