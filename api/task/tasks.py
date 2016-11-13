from django.core.exceptions import ObjectDoesNotExist
from celery import states
from logging import getLogger
from requests.exceptions import RequestException

from que.tasks import cq
from que.exceptions import TaskException
from que.internal import InternalTask
from que.utils import user_id_from_task_id
from api.task.utils import task_log, callback, get_vms_object, get_task_status
from api.task.cleanup import task_cleanup
from api.task.messages import LOG_REMOTE_CALLBACK
from api.task.callback import UserCallback
from gui.models import User

__all__ = ('task_log_cb', 'task_user_callback_cb')

logger = getLogger(__name__)


def task_log_cb(result, task_id, task_status=None, msg='', vm=None, obj=None, cleanup=False, check_returncode=False,
                **kwargs):
    """
    Log callback -> logs finished task.
    """
    if vm:
        obj = vm

    if not obj:
        try:
            obj = get_vms_object(kwargs)
        except ObjectDoesNotExist:
            pass

    if cleanup:
        # Sometimes when an execute task fails with an exception or is revoked
        # we might need to run things that the callback would run. But now the
        # callback won't run so emergency cleanup should go into this function.
        try:
            logger.info('Running cleanup for task=%s with task_status=%s', task_id, task_status)
            task_cleanup(result, task_id, task_status, obj, **kwargs)
        except Exception as e:
            logger.exception(e)
            logger.error('Got exception (%s) when doing cleanup for task=%s, task_status=%s, obj=%s',
                         e, task_id, task_status, obj)

    if check_returncode:
        rc = result.get('returncode', None)

        if rc != 0:
            err = 'Got bad return code (%s)' % rc
            err_msg = result.get('message', None)

            if err_msg:
                err += ' Error: %s' % err_msg

            logger.error('Found nonzero returncode in result from %s. Error: %s', kwargs.get('apiview', msg), result)
            raise TaskException(result, err)

    task_log(task_id, msg, obj=obj, task_status=task_status, task_result=result)

    return result


def task_log_cb_success(*args, **kwargs):
    kwargs['task_status'] = states.SUCCESS
    return task_log_cb(*args, **kwargs)


def task_log_cb_error(*args, **kwargs):
    kwargs['task_status'] = states.FAILURE
    return task_log_cb(*args, **kwargs)


@cq.task(name='api.task.tasks.task_log_cb')
@callback()
def _task_log_cb(result, task_id, **kwargs):
    """
    Same as task_log_cb, but used as celery task.
    """
    return task_log_cb(result, task_id, **kwargs)


# noinspection PyUnusedLocal
@cq.task(name='api.task.tasks.task_user_callback_cb', base=InternalTask)
def task_user_callback_cb(task_id, parent_task_id, cb, **kwargs):
    """
    Task for calling remote url in user defined callback
    """
    try:
        obj = get_vms_object(kwargs)
    except ObjectDoesNotExist:
        obj = None

    user = User.objects.get(id=user_id_from_task_id(parent_task_id))
    payload, status = get_task_status(parent_task_id)

    try:
        response = UserCallback(parent_task_id).request(cb, user.callback_key, payload)
    except RequestException as ex:
        status = states.FAILURE
        details = ex
    else:
        status = states.SUCCESS
        details = str(response.status_code) + ': ' + response.reason

    if cb.get('cb_log'):
        task_log(parent_task_id, LOG_REMOTE_CALLBACK, obj=obj, task_status=status, detail=details)
