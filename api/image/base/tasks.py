from time import time

from gevent import sleep

from vms.models import Image, Snapshot
from que.tasks import cq, get_task_logger
from que.mgmt import MgmtCallbackTask
from que.exceptions import TaskException
from que.user_tasks import UserTasks
from api.task.utils import callback
from api.task.tasks import task_log_cb_success

__all__ = ('image_manage_cb',)

logger = get_task_logger(__name__)

DELETE_NODE_IMAGE_TASKS_CHECK_TIMEOUT = 600


# noinspection PyUnusedLocal
def _image_manage_cb_failed(result, task_id, img, action, snap=None):
    """Callback helper for failed task"""
    if action == 'POST':
        img.delete()

        if snap:
            snap.save_status(Image.OK)

    elif action == 'PUT':
        img.status = Image.OK
        img.manifest = img.manifest_active
        img.save()

    elif action == 'DELETE':
        img.save_status(Image.OK)


@cq.task(name='api.image.base.tasks.image_manage_cb', base=MgmtCallbackTask, bind=True)
@callback()
def image_manage_cb(result, task_id, image_uuid=None, vm_uuid=None, snap_id=None, delete_node_image_tasks=None):
    """
    A callback function for api.image.base.views.image_manage and api.image.base.views.image_snapshot.
    """
    img = Image.objects.select_related('dc_bound', 'owner').get(uuid=image_uuid)
    apiview = result['meta']['apiview']
    action = apiview['method']
    json = result.pop('json', None)

    if snap_id:
        snap = Snapshot.objects.get(id=snap_id)
    else:
        snap = None

    if result['returncode'] == 0:
        if action == 'POST':
            if vm_uuid:  # save json from esimg if image_snapshot view is called
                try:
                    data = img.json.load(json)
                except Exception as e:
                    # The image won't be usable, but we wont raise an exception
                    logger.error('Could not parse json output from POST image_snapshot(%s, %s, %s). Error: %s',
                                 vm_uuid, snap_id, img, e)
                else:
                    img.manifest = data

            img.status = Image.OK
            img.manifest_active = img.manifest
            img.save()

            if snap:
                snap.save_status(Image.OK)

        elif action == 'PUT':
            img.status = Image.OK
            img.manifest_active = img.manifest
            img.save()

        elif action == 'DELETE':
            if delete_node_image_tasks:
                logger.info('Image %s must be deleted from node storage by DELETE node_image tasks: %s',
                            img, delete_node_image_tasks)
                delete_node_image_tasks = set(delete_node_image_tasks)
                start_time = time()

                while delete_node_image_tasks:
                    for tid in tuple(delete_node_image_tasks):  # copy so we do not iterate over something that changes
                        if UserTasks.exists(tid):
                            logger.info('DELETE node_image task ID %s seems to be still running. Check later...', tid)
                            sleep(1)
                        else:
                            logger.info('DELETE node_image task ID %s is not running anymore. OK...', tid)
                            delete_node_image_tasks.remove(tid)

                    if (time() - start_time) > DELETE_NODE_IMAGE_TASKS_CHECK_TIMEOUT:
                        logger.error('Timeout while waiting for DELETE node_image (%s) tasks to finish: %s',
                                     img, delete_node_image_tasks)
                        break

            img.delete()

    else:
        _image_manage_cb_failed(result, task_id, img, action, snap=snap)  # Rollback
        msg = result.get('message', '')
        logger.error('Found nonzero returncode in result from %s %s(%s, %s, %s). Error: %s',
                     action, apiview['view'], img, vm_uuid, snap_id, msg)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg), obj=img)

    task_log_cb_success(result, task_id, obj=img, **result['meta'])

    return result
