from logging import getLogger
from time import time, sleep

from que.user_tasks import UserTasks

logger = getLogger(__name__)

DELETE_NODE_IMAGE_TASKS_CHECK_TIMEOUT = 120


def wait_for_delete_node_image_tasks(img, delete_node_image_tasks, timeout=DELETE_NODE_IMAGE_TASKS_CHECK_TIMEOUT):
    """Used by DELETE image_manage because an image must be first deleted from node storages before it can be deleted"""
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

            if (time() - start_time) > timeout:
                logger.error('Timeout while waiting for DELETE node_image (%s) tasks to finish: %s',
                             img, delete_node_image_tasks)
                return False  # timeout -> some DELETE node_image tasks are still running

    return True  # nothing to wait for -> everything finished
