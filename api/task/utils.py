from logging import getLogger
from functools import wraps

from celery import states
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.contenttypes.models import ContentType
from django.utils.decorators import available_attrs
from django.utils.six import string_types
from gevent import sleep

from que import TT_ERROR
from que.tasks import cq
from que.lock import TaskLock
from que.utils import (is_dummy_task, task_prefix_from_task_id, task_id_from_request, dc_id_from_task_id,
                       follow_callback, get_result, cancel_task as _cancel_task, delete_task as _delete_task)
from que.exceptions import TaskException
from que.user_tasks import UserTasks
from api import status
from api.exceptions import OPERATIONAL_ERRORS
from api.decorators import catch_exception
from api.task.log import log, task_type_from_task_prefix, task_flag_from_task_msg
from api.task.callback import UserCallback
from api.task.messages import LOG_API_FAILURE
from vms.models import TASK_MODEL_KEYS
# noinspection PyProtectedMember
from vms.models.base import _UserTasksModel
from gui.models import User

logger = getLogger(__name__)

TASK_STATE = {
    states.PENDING: status.HTTP_201_CREATED,
    states.STARTED: status.HTTP_201_CREATED,
    states.SUCCESS: status.HTTP_200_OK,
    states.FAILURE: status.HTTP_400_BAD_REQUEST,
    states.RETRY: status.HTTP_205_RESET_CONTENT,  # Not used
    states.REVOKED: status.HTTP_410_GONE,
}

TASK_STATE_PENDING = frozenset([states.PENDING, states.STARTED, states.RETRY])

TASK_EXCEPTION = {
    'default': status.HTTP_500_INTERNAL_SERVER_ERROR,
    cq.AsyncResult.TimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
    cq.backend.redis.ConnectionError: status.HTTP_502_BAD_GATEWAY,
}

TASK_PARENT_STATUS_MAXWAIT = 15

MGMT_LOCK_TIMEOUT = cq.conf.ERIGONES_TASK_DEFAULT_EXPIRES


def _get_task_state(task):
    """Helper for retrieving task.state"""
    state = task.state

    if state == states.RETRY:
        return states.PENDING

    return state


def get_task_status_code(task, success_code=None):
    """
    Return response status code according to task status.
    """
    state = _get_task_state(task)

    if state == states.SUCCESS and success_code:
        return success_code

    return TASK_STATE[state]


def get_task_error(msg=None):
    """
    Return response dict for non-existent or error task.
    """
    if msg is None:
        r = {'detail': 'Task does not exist (anymore)'}
        s = status.HTTP_404_NOT_FOUND
    else:
        r = {'detail': msg}
        s = status.HTTP_400_BAD_REQUEST

    return r, s


def get_task_exception(ex):
    """
    Return response dict and status code according to Exception.
    """
    r = {'detail': ex.__class__.__name__ + ': ' + str(ex)}
    s = TASK_EXCEPTION.get(ex.__class__, TASK_EXCEPTION['default'])

    return r, s


def get_task_result(task, task_id):
    """
    Convert Celery Task Object into dict.
    """
    # get result dict
    result = get_result(task)
    state = _get_task_state(task)

    if state in TASK_STATE_PENDING:  # Hide STARTED result
        result = None
    elif isinstance(result, dict):
        # Let's make a copy, because we will later remove 'meta' and this will
        # happen in memory. So if someone uses this same reference, we could have a
        # problem. See #105
        result = result.copy()
        try:
            del result['meta']
        except KeyError:
            pass
        try:
            del result['json']
        except KeyError:
            pass

    tr = {
        'task_id': task_id,
        'status': state,
        'result': result,
    }

    return tr


def get_task_successful(task, task_id):
    """
    Convert Celery Task Object into dict.
    """
    tr = {
        'task_id': task_id,
        'done': task.successful(),
    }

    return tr


def get_task_status(task_id=None, method=get_task_result):
    """
    Abstract class for handling task status.
    """
    if task_id and not is_dummy_task(task_id):
        try:
            t = follow_callback(task_id)
        except Exception as e:
            r, s = get_task_exception(e)
        else:
            # noinspection PyBroadException
            try:
                c = t.result['meta'].pop('status', None)
            except:
                c = None
            try:
                s = get_task_status_code(t, c)
            except Exception as e:
                r, s = get_task_exception(e)
            else:
                r = method(t, task_id)
    else:
        r, s = get_task_error(None)

    return r, s


# noinspection PyBroadException
def get_task_error_message(task_result):
    """
    Parse error message from task result.
    """
    try:
        res = task_result['result']
    except:
        res = task_result

    for key in ('detail', 'message'):
        try:
            return res[key]
        except:
            continue

    return str(res)


def get_vms_object(kwargs):
    """
    Search vms identifier in kwargs and try to get the object or raise DoesNotExist exception.
    """
    for k in TASK_MODEL_KEYS:
        v = kwargs.get(k, None)

        if v:
            model = k.split('_')[0]
            cls = ContentType.objects.get(app_label='vms', model=model).model_class()
            return cls.objects.get(pk=v)

    raise ObjectDoesNotExist


# noinspection PyShadowingNames
def callback(log_exception=True, update_user_tasks=True, check_parent_status=True, error_fun=None, **meta_kwargs):
    """
    Decorator for celery task callbacks.
    """
    def wrap(fun):
        @wraps(fun, assigned=available_attrs(fun))
        def inner(task_obj, result, task_id, *args, **kwargs):
            try:  # Just in case, there will be probably no callback information at this point
                del result['meta']['callback']
            except KeyError:
                pass

            result['meta']['caller'] = task_id

            if meta_kwargs:
                result['meta'].update(meta_kwargs)

            # Issue #chili-512
            # + skipping checking of parent task status when task is being retried
            if check_parent_status and not task_obj.request.retries:
                cb_name = fun.__name__
                logger.debug('Waiting for parent task %s status, before running %s', task_id, cb_name)
                timer = 0

                while timer < TASK_PARENT_STATUS_MAXWAIT:
                    ar = cq.AsyncResult(task_id)
                    if ar.ready():
                        logger.info('Parent task %s has finished with status=%s. Running %s',
                                    task_id, ar.status, cb_name)
                        break

                    timer += 1
                    logger.warning('Whoa! Parent task %s has not finished yet with status=%s. Waiting 1 second (%d), '
                                   'before running %s', task_id, ar.status, timer, cb_name)
                    sleep(1.0)
                else:
                    logger.error('Task %s is not ready. Running %s anyway :(', task_id, cb_name)

            try:
                return fun(result, task_id, *args, **kwargs)
            except OPERATIONAL_ERRORS as exc:
                raise exc  # Caught by que.mgmt.MgmtCallbackTask
            except Exception as e:
                logger.exception(e)
                logger.error('Task %s failed', task_id)

                if not isinstance(e, TaskException):
                    e = TaskException(result, str(e))

                if log_exception or update_user_tasks:
                    if e.obj is None:
                        try:
                            obj = get_vms_object(kwargs)
                        except ObjectDoesNotExist:
                            obj = None
                            # noinspection PyProtectedMember
                            _UserTasksModel._tasks_del(task_id)  # Always remove user task
                    else:
                        obj = e.obj

                    if log_exception:
                        msg = e.result['meta'].get('msg', '')
                        # Also removes user task in task_log
                        task_log(task_id, msg, obj=obj, task_status=states.FAILURE, task_result=e.result)
                    elif obj:  # update_user_tasks
                        obj.tasks_del(task_id)

                if error_fun:
                    try:
                        error_fun(result, task_id, task_exception=e, *args, **kwargs)
                    except Exception as ex:
                        logger.exception(ex)

                raise e

            finally:
                cb = UserCallback(task_id).load()

                if cb:
                    logger.debug('Creating task for UserCallback[%s]: %s', task_id, cb)
                    from api.task.tasks import task_user_callback_cb  # Circular import
                    task_user_callback_cb.call(task_id, cb, **kwargs)

        return inner
    return wrap


def mgmt_lock(timeout=MGMT_LOCK_TIMEOUT, key_args=(), key_kwargs=(), wait_for_release=False, bound_task=False):
    """
    Decorator for runtime task locks.
    This means that task will run, but will wait in a loop until it acquires a lock or will fail if timeout is reached.
    """
    def wrap(fun):
        @wraps(fun, assigned=available_attrs(fun))
        def inner(*args, **kwargs):
            if bound_task:
                params = args[1:]  # The first parameter is a celery task/request object
            else:
                params = args

            task_id = params[0]
            task_name = fun.__name__
            lock_keys = [task_name]
            lock_keys.extend(str(params[i]) for i in key_args)
            lock_keys.extend(str(kwargs[i]) for i in key_kwargs)
            task_lock = TaskLock(':'.join(lock_keys), desc='Task %s' % task_name)

            def acquire_lock():
                return task_lock.acquire(task_id, timeout=timeout, save_reverse=False)

            if not acquire_lock():
                existing_lock = task_lock.get()

                if wait_for_release:
                    logger.warn('Task %s(%s, %s) must wait (%s), because another task %s is already running',
                                task_name, args, kwargs, timeout or 'forever', existing_lock)
                    wait = 0

                    while wait < timeout:
                        sleep(3)
                        wait += 3

                        if acquire_lock():
                            break
                    else:
                        logger.warn('Task %s(%s, %s) will not run, because another task %s is still running and we have'
                                    ' waited for too long (%s)', task_name, args, kwargs, existing_lock, wait)
                        return
                else:
                    logger.warn('Task %s(%s, %s) will not run, because another task %s is already running',
                                task_name, args, kwargs, existing_lock)
                    return

            try:
                return fun(*args, **kwargs)
            finally:
                task_lock.delete(fail_silently=True, delete_reverse=False)

        return inner
    return wrap


def mgmt_task(update_user_tasks=True):
    """
    Decorator for celery standalone mgmt tasks.
    """
    def wrap(fun):
        @wraps(fun, assigned=available_attrs(fun))
        def inner(task_id, *args, **kwargs):
            try:
                return fun(task_id, *args, **kwargs)
            except Exception as e:
                logger.exception(e)
                logger.error('Mgmt Task %s failed', task_id)
                raise e
            finally:
                if update_user_tasks:
                    try:
                        obj = get_vms_object(kwargs)
                    except ObjectDoesNotExist:
                        # noinspection PyProtectedMember
                        _UserTasksModel._tasks_del(task_id)
                    else:
                        obj.tasks_del(task_id)
        return inner
    return wrap


# noinspection PyUnusedLocal,PyUnboundLocalVariable
@catch_exception
def task_log(task_id, msg, vm=None, obj=None, user=None, api_view=None, task_status=None, task_result=None,
             owner=None, time=None, detail=None, update_user_tasks=True, dc_id=None, **kwargs):
    """
    Create task log read by the user. Also maintain dictionary of active tasks for specific VM.
    """
    task_id = str(task_id)
    task_prefix = task_prefix_from_task_id(task_id)
    dc_id = dc_id or int(task_prefix[4])  # Specifying a custom dc_id is usually not a good idea
    update_tasks = False

    # When? (time)
    if not time:
        time = timezone.now()

    # Who? (username, task creator)
    if user and not isinstance(user, string_types):
        username = user.username
        user_id = user.id
    else:
        user = None
        user_id = int(task_prefix[0])
        if user_id == int(cq.conf.ERIGONES_TASK_USER):
            username = cq.conf.ERIGONES_TASK_USERNAME
        else:
            try:
                username = User.objects.get(id=user_id).username
            except User.DoesNotExist:
                username = '_unknown_'

    # What? (status and result)
    if not task_status or not task_result:
        # Do not follow callback here, because we are called from pending callbacks
        task = cq.AsyncResult(task_id)
        if not task_status:
            task_status = task.state
        if not task_result:
            task_result = task.result

    # Object? (Vm, Node, ...)
    if vm:
        obj = vm

    if obj and isinstance(obj, (tuple, list)):
        object_name = obj[0]
        object_alias = obj[1]
        object_pk = obj[2]
        content_type = ContentType.objects.get_for_model(obj[3])
        object_type = content_type.model
        obj = None
    elif obj and not isinstance(obj, string_types):
        object_name = obj.log_name
        object_alias = obj.log_alias
        object_pk = obj.pk
        content_type = ContentType.objects.get_for_model(obj)
        object_type = content_type.model

        if update_user_tasks and hasattr(obj, 'tasks'):
            update_tasks = True

    else:
        if obj:
            object_name = str(obj)
        else:
            object_name = ''

        object_alias = ''
        object_pk = ''
        obj = None
        content_type = None
        object_type = None

    if object_pk is None:
        object_pk = ''
    else:
        object_pk = str(object_pk)

    # Detail?
    if not detail:
        if task_result:
            # noinspection PyBroadException
            try:
                detail = task_result['detail']
            except:
                # noinspection PyBroadException
                try:
                    detail = task_result['message']
                except:
                    detail = ''
        if detail is None:
            detail = ''

    # Owner?
    if not owner:
        if obj:
            # noinspection PyBroadException
            try:
                owner = obj.owner
            except:
                owner = user
        elif user:
            owner = user

    # noinspection PyBroadException
    try:
        owner_id = owner.id
    except:
        owner_id = int(task_prefix[2])

    if task_status == states.STARTED:
        task_status = states.PENDING

    try:  # Log!
        log({
            'dc_id': dc_id,
            'time': time,
            'task': task_id,
            'status': task_status,
            'task_type': task_type_from_task_prefix(task_prefix),
            'flag': task_flag_from_task_msg(msg),
            'user_id': user_id,
            'username': username,
            'owner_id': owner_id,
            'object_pk': object_pk,
            'object_type': object_type,
            'object_name': object_name,
            'object_alias': object_alias,
            'content_type': content_type,
            'msg': msg,
            'detail': detail,
        })
    finally:
        if update_tasks:  # Save task info into UserTasks cache after the task was logged
            try:
                if task_status in TASK_STATE_PENDING:
                    obj.tasks_add(task_id, api_view, msg=msg, time=time.isoformat())

                    return True
                else:
                    obj.tasks_del(task_id)
            except Exception as e:
                logger.exception(e)
                logger.error('Got exception (%s) when updating task %s for %s.', e, task_id, obj)

    return None


def task_log_error(*args, **kwargs):
    """
    Log task error.
    """
    kwargs['task_status'] = states.FAILURE
    task_log(*args, **kwargs)


def task_log_success(*args, **kwargs):
    """
    Log task success.
    """
    kwargs['task_status'] = states.SUCCESS
    task_log(*args, **kwargs)


def task_log_exception(request, exc, task_id=None, **kwargs):
    """
    Log API exception.
    """
    if not task_id:
        task_id = task_id_from_request(request, tt=TT_ERROR, dummy=True)

    task_result, task_status = get_task_exception(exc)
    task_log_error(task_id, LOG_API_FAILURE, user=request.user, task_result=task_result, task_status=task_status,
                   update_user_tasks=False, **kwargs)


def get_user_tasks(request, filter_fun=None):
    """
    Return list of all user tasks in current datacenter. If user is staff or DC owner then return all tasks.
    List can be filtered by filter_function.
    """
    user_tasks = UserTasks(request.user.id)

    if request.user.is_admin(request):
        tasks = user_tasks.tasklist_all
    else:
        tasks = user_tasks.tasklist

    # Always filter tasks for current datacenter
    dc_id = str(request.dc.id)
    tasks = set([t for t in tasks if dc_id_from_task_id(t) == dc_id])

    if filter_fun:
        return filter(filter_fun, tasks)
    else:
        return tasks


def cancel_task(task_id, force=False):
    """
    Revoke task.
    """
    if force:
        signal = 'SIGKILL'
    else:
        signal = 'SIGTERM'

    return _cancel_task(task_id, terminate=True, signal=signal)


def delete_task(task_id, force=False):
    """
    Delete task. It's like cancel, but only for tasks which started, but failed to finish and are stuck in DB.
    """
    return _delete_task(task_id, force=force)


def get_system_task_user(request=None):
    """
    Return ERIGONES_TASK_USER User object.
    """
    _system = User.objects.get(pk=int(cq.conf.ERIGONES_TASK_USER))

    if request:
        from django.contrib.auth.views import login
        _system.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, _system)

    return _system


class TaskID(str):
    """
    Task ID wrapper.
    """
    # noinspection PyInitNewSignature
    def __new__(cls, value, request=None):
        obj = str.__new__(cls, value)

        if request:
            obj.__dict__.update(request.__dict__)

        return obj

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self)

    @property
    def prefix(self):
        return task_prefix_from_task_id(self)
