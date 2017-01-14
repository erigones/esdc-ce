from que import TG_DC_UNBOUND
from que.tasks import cq, get_task_logger, execute
from que.mgmt import MgmtCallbackTask
from que.exceptions import TaskException
from vms.models import Node, NodeStorage, Image, ImageVm
from api.task.tasks import task_log_cb_success
from api.task.utils import callback, mgmt_lock
from api.task.internal import InternalTask
from api.node.messages import LOG_IMG_IMPORT, LOG_IMG_DELETE

__all__ = ('node_image_cb',)

logger = get_task_logger(__name__)

ERIGONES_TASK_USER = cq.conf.ERIGONES_TASK_USER


# noinspection PyUnusedLocal
def _node_image_cb_failed(result, task_id, ns, img):
    """
    Callback helper for failed task - remove image nodestorage pending status.
    """
    img.del_ns_status(ns)


@cq.task(name='api.node.image.tasks.node_image_cb', base=MgmtCallbackTask, bind=True)
@callback()
def node_image_cb(result, task_id, nodestorage_id=None, zpool=None, img_uuid=None):
    """
    A callback function for api.node.image.views.node_image.
    """
    ns = NodeStorage.objects.select_related('node').get(id=nodestorage_id)
    img = Image.objects.get(uuid=img_uuid)
    img.del_ns_status(ns)
    method = result['meta']['apiview']['method']
    msg = result.get('message', '')
    log_msg = None
    result.pop('stderr', None)

    if result['returncode'] == 0:
        if method == 'POST':
            if 'Imported image' in msg or 'is already installed, skipping' in msg:
                ns.images.add(img)
                log_msg = LOG_IMG_IMPORT

        elif method == 'DELETE':
            if 'Deleted image' in msg:
                ns.images.remove(img)
                log_msg = LOG_IMG_DELETE

        if log_msg:
            task_log_cb_success(result, task_id, msg=log_msg, obj=ns)
            ns.update_resources(recalculate_vms_size=False, recalculate_backups_size=False,
                                recalculate_images_size=True)
            return result

    logger.error('Found nonzero returncode in result from %s node_image(%s, %s, %s). Error: %s',
                 method, nodestorage_id, zpool, img_uuid, msg)
    raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg))


def run_node_img_sources_sync(node, new_img_sources=None, node_img_sources=None):
    """
    Update imgadm sources on compute node.
    Called by
    """
    if new_img_sources is None:
        image_vm = ImageVm()
        new_img_sources = image_vm.sources

    if node_img_sources is not None and new_img_sources == node_img_sources:
        logger.info('Image sources already synced for node %s - skipping update', node)
        return

    logger.warn('Image sources are not synchronized on node %s - creating imgadm sources synchronization task', node)
    stdin = ImageVm.get_imgadm_conf(new_img_sources).dump()
    cmd = 'cat /dev/stdin > /var/imgadm/imgadm.conf'
    lock = 'node %s imgadm_sources' % node.uuid

    tid, err = execute(ERIGONES_TASK_USER, None, cmd, stdin=stdin, callback=False, lock=lock, queue=node.fast_queue,
                       expires=180, nolog=True, tg=TG_DC_UNBOUND, ping_worker=False, check_user_tasks=False)
    if err:
        logger.error('Got error (%s) when running task %s for updating imgadm sources on node %s', err, tid, node)
    else:
        logger.info('Created task %s for updating imgadm sources on node %s', tid, node)


# noinspection PyUnusedLocal
@cq.task(name='api.node.image.tasks.node_img_sources_sync', base=InternalTask)
@mgmt_lock(timeout=3600, wait_for_release=True)
def node_img_sources_sync(task_id, sender, **kwargs):
    """
    Task for updating imgadm sources on one or every compute node.
    Called by dc_settings_changed signal.
    """
    new_img_sources = ImageVm().sources

    for node in Node.all():
        # We update imgadm sources only on online nodes
        # But we will also run run_node_img_sources_sync() whenever node status is changed to online because
        # the node_startup handler runs the sysinfo update task
        if not node.is_online():
            logger.warn('Excluding node %s from updating imgadm sources because it is not in online state', node)
            continue

        run_node_img_sources_sync(node, new_img_sources=new_img_sources)
