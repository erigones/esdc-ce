from django.conf import settings

from api.signals import node_status_changed, node_unreachable, node_online
from api.task.utils import task_log_success, mgmt_lock
from api.task.internal import InternalTask
from api.node.messages import LOG_STATUS_UPDATE
from api.node.status.utils import node_ping
from api.vm.status.tasks import vm_status_all
from vms.models import Node
from vms.signals import node_check
from que import Q_FAST, Q_IMAGE
from que.tasks import cq, get_task_logger


__all__ = ('node_worker_status_update',)

logger = get_task_logger(__name__)


# noinspection PyUnusedLocal
@cq.task(name='api.node.status.tasks.node_worker_status_update', base=InternalTask)
@mgmt_lock(timeout=3600, key_args=(1,), wait_for_release=True)
def node_worker_status_update(task_id, hostname, queue=None, status=None, **kwargs):
    """Check (ping) and update compute node status (called by MgmtDaemon)"""
    logger.debug('Received %s (%s) node worker status: %s', hostname, queue, status)

    if settings.DEBUG:
        logger.warning('DEBUG mode on => skipping status checking of node worker %s@%s', queue, hostname)
        return

    try:
        node = Node.objects.get(hostname=hostname)
    except Node.DoesNotExist:
        logger.warn('Node with hostname=%s does not exist in DB (yet?)', hostname)
        return

    if node.is_initializing():
        logger.info('Node %s is being initialized. Ignoring %s status update', node, status)
        return

    node_is_online = node.is_online()
    node_is_unreachable = node.is_unreachable()

    if not ((status == 'online' and node_is_unreachable) or
            (status == 'offline' and node_is_online) or
            (status == 'unknown' and (node_is_online or node_is_unreachable))):
        logger.info('Node %s is already %s. Ignoring %s status update', node, node.get_status_display(), status)
        return

    logger.info('Double-checking %s node status by using ping', node)
    new_status = None
    up = None

    if status == 'online':
        up = node_ping(node, count=5, all_workers=False, all_up=True)  # fast and image worker must be up
        if up:
            new_status = Node.ONLINE
    elif status == 'offline':
        up = node_ping(node, count=3, all_workers=False, all_up=True)  # fast or image worker must be down
        if not up:
            new_status = Node.UNREACHABLE
    elif status == 'unknown':
        up = node_ping(node, count=3, all_workers=False, all_up=True)  # fast and image worker must be up

        if up and node_is_unreachable:
            new_status = Node.ONLINE
        elif not up and node_is_online:
            new_status = Node.UNREACHABLE

    if new_status:
        logger.warn('All node %s workers are %s. Node %s status is serious', node, 'up' if up else 'down', status)
        node.save_status(new_status)
        logger.warn('Switched node %s status to %s', node, node.get_status_display())
        task_log_success(task_id, LOG_STATUS_UPDATE, obj=node, detail='status="%s"' % node.get_status_display(),
                         update_user_tasks=False)
        node_status_changed.send(task_id, node=node, automatic=True)  # Signal!

        if node.is_online():
            node_online.send(task_id, node=node, automatic=True)  # Signal!
        elif node.is_unreachable():
            node_unreachable.send(task_id, node=node)  # Signal!

    else:
        logger.warn('At least one node %s worker is still up/down. Ignoring %s, status update', node, status)


# noinspection PyUnusedLocal
@cq.task(name='api.node.status.tasks.node_worker_status_check_all', base=InternalTask)
@mgmt_lock(timeout=60, wait_for_release=True)
def node_worker_status_check_all(task_id, **kwargs):
    """Run node_worker_status_update() for all licensed compute nodes; called by que.handlers.mgmt_worker_start"""
    if settings.DEBUG:
        logger.warning('DEBUG mode on => skipping status checking of all node workers')
        return

    for node in Node.objects.exclude(status__in=(Node.UNLICENSED, Node.OFFLINE)):
        node_worker_status_update.call(node.hostname, queue=Q_FAST, status='unknown')
        vm_status_all(task_id, node)  # Also run VM status checks on compute node


# noinspection PyUnusedLocal
def node_worker_status_change(hostname, queue, status, event):
    """Called by MgmtDaemon worker status monitor for all worker-online/offline events"""
    if queue in (Q_FAST, Q_IMAGE):
        node_worker_status_update.call(hostname, queue=queue, status=status)


def node_status_all():
    """
    This is a special periodic task, run by Danube Cloud mgmt daemon (que.bootsteps.MgmtDaemon) every minute.
    It is responsible for running checks on an unreachable compute node.
    """
    for node in Node.all():
        if node.is_unreachable():
            logger.info('Checking status of unreachable node %s', node)
            node_worker_status_update.call(node.hostname, queue=Q_FAST, status='unknown')

        node_check.send('node_status_all', node=node)  # Signal!
