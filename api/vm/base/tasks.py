from gevent import sleep

from que.tasks import cq, get_task_logger
from que.mgmt import MgmtCallbackTask
from que.utils import user_id_from_task_id
from que.exceptions import TaskException
from gui.models import User
from vms.models import Vm, Snapshot, SnapshotDefine, BackupDefine, Node
from vms.signals import vm_created, vm_deployed, vm_notcreated, vm_json_active_changed, vm_node_changed
from api.email import sendmail
from api.utils.request import get_dummy_request
from api.task.tasks import task_log_cb_success, task_log_cb_error
from api.task.utils import callback
from api.vm.base.utils import (is_vm_missing, vm_update_ipaddress_usage, vm_delete_snapshots_of_removed_disks,
                                vm_reset, vm_update)
from api.vm.status.tasks import vm_status_changed, vm_status_one
from api.vm.snapshot.vm_define_snapshot import SnapshotDefineView
from api.vm.backup.vm_define_backup import BackupDefineView

__all__ = ('vm_create_cb', 'vm_update_cb', 'vm_delete_cb', 'vm_deploy_cb')

logger = get_task_logger(__name__)

VMS_VM_DEPLOY_TOOLONG = 600
VMS_VM_DEPLOY_TOOLONG_MAX_CYCLES = 1


def _vm_create_cb_failed(result, task_id, vm, inform_user=True):
    """
    Callback helper for failed task - revert status and inform user.
    """
    # revert status
    if result['meta']['apiview']['recreate']:
        if result['message'].find('Successfully deleted') == 0:
            Snapshot.objects.filter(vm=vm).delete()
            SnapshotDefine.objects.filter(vm=vm).delete()
            BackupDefine.objects.filter(vm=vm).delete()
            vm.save_metadata('installed', False, save=True, update_fields=('enc_json', 'changed'))
            revert_state = Vm.NOTCREATED
        else:
            revert_state = Vm.STOPPED
    else:
        revert_state = Vm.NOTCREATED
    # save reverted status and inform user
    if inform_user:
        if vm.status != revert_state:
            vm_status_changed(task_id, vm, revert_state, save_state=True)
    else:
        vm.status = revert_state
        vm.save_status()


# noinspection PyUnusedLocal
def _vm_update_cb_done(result, task_id, vm):
    """
    Callback helper for failed task - revert status.
    """
    vm.revert_notready()


# noinspection PyUnusedLocal
def _vm_delete_cb_failed(result, task_id, vm):
    """
    Callback helper for failed task - revert status.
    """
    vm.revert_notready()


def _vm_delete_cb_succeeded(task_id, vm):
    """
    Helper function used by vm_delete_cb to run proper vm methods in order to delete the VM.
    """
    vm.status = Vm.NOTCREATED
    vm.json_active = {}
    # Let's update resource counters, because they depend on Vm.is_deployed() status and json_active
    vm.save(update_node_resources=True, update_storage_resources=True)
    vm_update_ipaddress_usage(vm)
    Snapshot.objects.filter(vm=vm).delete()
    SnapshotDefine.objects.filter(vm=vm).delete()
    BackupDefine.objects.filter(vm=vm).delete()
    vm_notcreated.send(task_id, vm=vm)  # Signal!


def _vm_error(task_id, vm):
    """
    Helper function for vm_create_cb -> sets VM to ERROR state and runs real status detection.
    """
    vm.status = vm.ERROR
    vm.save_status()
    vm_status_one(task_id, vm)


@cq.task(name='api.vm.base.tasks.vm_create_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_create_cb(result, task_id, vm_uuid=None):
    """
    A callback function for api.vm.base.views.vm_manage.
    """
    vm = Vm.objects.select_related('dc').get(uuid=vm_uuid)
    msg = result.get('message', '')

    if result['returncode'] == 0 and msg.find('Successfully created') >= 0:
        json = result.pop('json', None)

        try:  # save json from smartos
            json_active = vm.json.load(json)
            vm.json_active = json_active
            vm.json = json_active
            if result['meta']['apiview']['recreate']:
                Snapshot.objects.filter(vm=vm).delete()
                SnapshotDefine.objects.filter(vm=vm).delete()
                BackupDefine.objects.filter(vm=vm).delete()
                vm.save_metadata('installed', False, save=False)

        except Exception as e:
            logger.error('Could not parse json output from POST vm_manage(%s). Error: %s', vm_uuid, e)
            _vm_error(task_id, vm)
            logger.exception(e)
            raise TaskException(result, 'Could not parse json output')

        else:
            # save all
            vm.save(update_node_resources=True, update_storage_resources=True)
            vm_update_ipaddress_usage(vm)
            # vm_json_active_changed.send(task_id, vm=vm)  # Signal! -> not needed because vm_deployed is called below
            vm_created.send(task_id, vm=vm)  # Signal!

            if msg.find('Successfully started') < 0:  # VM was created, but could not be started
                logger.error('VM %s was created, but could not be started! Error: %s', vm_uuid, msg)
                _vm_error(task_id, vm)
                raise TaskException(result, 'Initial start failed (%s)' % msg)

            sendmail(vm.owner, 'vm/base/vm_create_subject.txt', 'vm/base/vm_create_email.txt',
                     extra_context={'vm': vm}, user_i18n=True, dc=vm.dc, fail_silently=True)

    else:
        logger.error('Found nonzero returncode in result from POST vm_manage(%s). Error: %s', vm_uuid, msg)
        # Revert status and inform user
        _vm_create_cb_failed(result, task_id, vm)

        if result['meta']['apiview']['recreate'] and msg.find('Successfully deleted') >= 0:
            _vm_error(task_id, vm)  # Something went terribly wrong

        # and FAIL this task
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg))

    # So far so good. Now wait for deploy_over in vm_status_event_cb
    logger.info('VM %s is waiting for deploy_over...', vm_uuid)
    timer = 0
    repeat = 0

    while not vm.has_deploy_finished():
        if timer > VMS_VM_DEPLOY_TOOLONG:  # 10 minutes is too long
            if repeat == VMS_VM_DEPLOY_TOOLONG_MAX_CYCLES:  # 20 minutes is really too long
                logger.error('VM %s deploy process has timed out!', vm_uuid)
                _vm_error(task_id, vm)
                result['message'] = 'VM %s deploy has timed out' % vm.hostname
                task_log_cb_error(result, task_id, vm=vm, **result['meta'])
                return result

            repeat += 1
            timer = 0
            logger.error('VM %s takes too long to deploy. Sending force stop/start', vm_uuid)
            # noinspection PyUnusedLocal
            tid, err = vm_reset(vm)

        sleep(3.0)
        timer += 3

    logger.info('VM %s is completely deployed!', vm_uuid)
    internal_metadata = vm.json.get('internal_metadata', {}).copy()  # save internal_metadata for email
    vm = Vm.objects.select_related('dc', 'template').get(pk=vm.pk)  # Reload vm
    vm_deployed.send(task_id, vm=vm)  # Signal!
    sendmail(vm.owner, 'vm/base/vm_deploy_subject.txt', 'vm/base/vm_deploy_email.txt', fail_silently=True,
             extra_context={'vm': vm, 'internal_metadata': internal_metadata}, user_i18n=True, dc=vm.dc)

    try:
        result['message'] = '\n'.join(result['message'].strip().split('\n')[:-1])  # Remove "started" stuff
    except Exception as e:
        logger.exception(e)

    task_log_cb_success(result, task_id, vm=vm, **result['meta'])

    try:
        if vm.template:  # Try to create snapshot/backup definitions defined by template
            vm_define_snapshot, vm_define_backup = vm.template.vm_define_snapshot, vm.template.vm_define_backup

            if vm_define_snapshot or vm_define_backup:
                user = User.objects.get(id=user_id_from_task_id(task_id))
                request = get_dummy_request(vm.dc, method='POST', user=user)
                SnapshotDefineView.create_from_template(request, vm, vm_define_snapshot, log=logger)
                BackupDefineView.create_from_template(request, vm, vm_define_backup, log=logger)
    except Exception as e:
        logger.exception(e)

    return result


@cq.task(name='api.vm.base.tasks.vm_update_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_update_cb(result, task_id, vm_uuid=None, new_node_uuid=None):
    """
    A callback function for api.vm.base.views.vm_manage.
    """
    vm = Vm.objects.select_related('dc').get(uuid=vm_uuid)
    _vm_update_cb_done(result, task_id, vm)
    msg = result.get('message', '')
    force = result['meta']['apiview']['force']

    if result['returncode'] == 0 and (force or msg.find('Successfully updated') >= 0):
        json = result.pop('json', None)

        try:  # save json from smartos
            json_active = vm.json.load(json)
        except Exception as e:
            logger.exception(e)
            logger.error('Could not parse json output from PUT vm_manage(%s). Error: %s', vm_uuid, e)
            raise TaskException(result, 'Could not parse json output')

        vm_delete_snapshots_of_removed_disks(vm)  # Do this before updating json and json_active
        vm.json = json_active
        update_fields = ['enc_json', 'enc_json_active', 'changed']
        ignored_changed_vm_attrs = (
            'set_customer_metadata',
            'remove_customer_metadata',
            'boot_timestamp',
            'autoboot',
            'vnc_port',
        )

        if new_node_uuid:
            update_dict = vm.json_update()

            for i in ignored_changed_vm_attrs:
                update_dict.pop(i, None)

            if update_dict:
                raise TaskException(result, 'VM definition on compute node differs from definition in DB in '
                                    'following attributes: %s' % ','.join(update_dict.keys()))
            update_fields.append('node_id')

        vm.json_active = json_active

        if new_node_uuid:
            node = Node.objects.get(uuid=new_node_uuid)
            vm.set_node(node)

        vm.save(update_node_resources=True, update_storage_resources=True, update_fields=update_fields)
        vm_update_ipaddress_usage(vm)
        vm_json_active_changed.send(task_id, vm=vm)  # Signal!

        if new_node_uuid:
            vm_node_changed.send(task_id, vm=vm, force_update=True)  # Signal!
            result['message'] = 'Node association successfully changed on VM %s' % vm.hostname
            if vm.json_changed():
                vm_update(vm)

    else:
        logger.error('Found nonzero returncode in result from PUT vm_manage(%s). Error: %s', vm_uuid, msg)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg))

    task_log_cb_success(result, task_id, vm=vm, **result['meta'])
    return result


@cq.task(name='api.vm.base.tasks.vm_delete_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_delete_cb(result, task_id, vm_uuid=None):
    """
    A callback function for api.vm.base.views.vm_manage.
    """
    vm = Vm.objects.select_related('dc').get(uuid=vm_uuid)
    msg = result.get('message', '')

    if result['returncode'] == 0 and msg.find('Successfully deleted') == 0:
        _vm_delete_cb_succeeded(task_id, vm)
    else:
        logger.error('Found nonzero returncode in result from DELETE vm_manage(%s). Error: %s', vm_uuid, msg)

        if is_vm_missing(vm, msg):
            logger.critical('VM %s has vanished from compute node!', vm_uuid)
            _vm_delete_cb_succeeded(task_id, vm)
        else:
            _vm_delete_cb_failed(result, task_id, vm)

        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg))

    task_log_cb_success(result, task_id, vm=vm, **result['meta'])
    return result


# noinspection PyUnusedLocal
@cq.task(name='api.vm.base.tasks.vm_deploy_cb', base=MgmtCallbackTask, bind=True)
@callback()
def vm_deploy_cb(result, task_id, vm_uuid=None):
    """
    A callback function for api.vm.base.views.vm_deploy.
    Do not task_log/raise anything here - it is used as a internal task.
    """
    if result['returncode'] == 0:
        vm = Vm.objects.get(uuid=vm_uuid)
        json = result.pop('json', None)
        try:
            # save json from smartos (again)
            json_active = vm.json.load(json)
            vm.json_active = json_active
            vm.json = json_active  # We will loose root_pw here
            vm.save(update_fields=('enc_json', 'enc_json_active', 'changed'))
            # vm_json_active_changed.send(task_id, vm=vm)  # Signal! -> not needed (already informed in vm_create_cb)
        except Exception as e:
            logger.exception(e)
            logger.error('Could not parse json output from vm_deploy(%s). Error: %s', vm_uuid, e)
    else:
        logger.error('Found nonzero returncode in result from vm_deploy(%s). Error: %s',
                     vm_uuid, result.get('message', ''))

    return result
