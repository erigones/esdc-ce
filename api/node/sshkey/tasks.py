from api.node.messages import LOG_NODE_UPDATE
from api.task.utils import callback, task_log_error, mgmt_lock
from api.task.internal import InternalTask
from vms.models import Node, DefaultDc
from que import TG_DC_UNBOUND
from que.tasks import cq, execute, get_task_logger
from que.mgmt import MgmtCallbackTask

__all__ = ('node_authorized_keys_sync', 'node_authorized_keys_sync_cb')

logger = get_task_logger(__name__)

ERIGONES_TASK_USER = cq.conf.ERIGONES_TASK_USER


def run_node_authorized_keys_sync():
    """
    Create and update authorized_keys on every compute node.
    """
    dc1_settings = DefaultDc().settings  # erigones.conf.settings

    if not dc1_settings.VMS_NODE_SSH_KEYS_SYNC:
        logger.warn('Node authorized_keys synchronization is disabled!')
        return

    nodes = Node.objects.all().order_by('hostname')
    # Create one authorized_keys list
    authorized_keys = [node.sshkey for node in nodes if node.sshkey]

    # Add user specified compute node SSH keys
    authorized_keys.extend(dc1_settings.VMS_NODE_SSH_KEYS_DEFAULT)

    # Save the authorized_keys file on every compute node to persistent /usbkey/config.inc/ and /root/.ssh locations
    files = '/usbkey/config.inc/authorized_keys /root/.ssh/authorized_keys'
    cmd = 'tee %s; chmod 640 %s' % (files, files)
    stdin = '\n'.join(authorized_keys)

    for node in nodes:
        if node.authorized_keys == stdin:
            logger.info('authorized_keys already synced for node %s - skipping update', node)
            continue

        # We update authorized_keys only on online nodes
        # But we will also run this whenever node status is changed to online
        if not node.is_online():
            logger.warn('Excluding node %s from updating authorized_keys because it is not in online state', node)
            continue

        lock = 'node %s authorized_keys' % node.uuid
        cb = ('api.node.sshkey.tasks.node_authorized_keys_sync_cb', {'node_uuid': node.uuid})
        tid, err = execute(ERIGONES_TASK_USER, None, cmd, stdin=stdin, callback=cb, lock=lock, queue=node.fast_queue,
                           expires=180, nolog=True, tg=TG_DC_UNBOUND, ping_worker=False, check_user_tasks=False)
        if err:
            logger.error('Got error (%s) when running task %s for updating authorized_keys on node %s', err, tid, node)
        else:
            logger.info('Created task %s for updating authorized_keys on node %s', tid, node)


# noinspection PyUnusedLocal
@cq.task(name='api.node.sshkey.tasks.node_authorized_keys_sync', base=InternalTask)
@mgmt_lock(timeout=3600, wait_for_release=True)
def node_authorized_keys_sync(task_id, sender, **kwargs):
    """
    Task for updating authorized_keys on each compute node (called via node_online signal).
    """
    run_node_authorized_keys_sync()


@cq.task(name='api.node.sshkey.tasks.node_authorized_keys_sync_cb', base=MgmtCallbackTask, bind=True)
@callback(log_exception=False, update_user_tasks=False)
def node_authorized_keys_sync_cb(result, task_id, node_uuid=None):
    """
    Callback for run_node_authorized_keys_sync().
    """
    node = Node.objects.get(uuid=node_uuid)

    if result['returncode'] == 0:
        node.save_authorized_keys(result['stdout'])
    else:
        result['message'] = 'Compute node SSH key sync error - got bad return code (%s). Error: %s' % \
                            (result['returncode'], result.get('stderr', ''))
        task_log_error(task_id, msg=LOG_NODE_UPDATE, obj=node, task_result=result, update_user_tasks=False)

    return result
