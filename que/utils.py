from __future__ import absolute_import

import re
import json
import hashlib
from uuid import UUID, uuid4
from ast import literal_eval
from time import sleep
from subprocess import Popen, PIPE
from logging import getLogger
from six import string_types
from celery import states
from celery.app.control import flatten_reply

from que import IMPORTANT, E_SHUTDOWN, Q_MGMT, TT_EXEC, TT_MGMT, TT_INTERNAL, TG_DC_BOUND
from que.erigonesd import cq
from que.lock import TaskLock
from que.user_tasks import UserTasks
from que.exceptions import PingFailed, NodeError

# Defaults
LOGTASK = cq.conf.ERIGONES_LOGTASK
TASK_USER = cq.conf.ERIGONES_TASK_USER
DEFAULT_DC = cq.conf.ERIGONES_DEFAULT_DC
DEFAULT_TASK_PREFIX = [None, TT_EXEC, '1', TG_DC_BOUND, DEFAULT_DC]

RE_TASK_PREFIX = re.compile(r'([a-zA-Z]+)')
DEFAULT_FILE_READ_SIZE = 102400

logger = getLogger(__name__)


def task_id_from_string(user_id, owner_id=None, dummy=False, tt=TT_EXEC, tg=TG_DC_BOUND,
                        dc_id=DEFAULT_DC, task_prefix=None):
    """
    Generate new task ID with prepended user ID.
    """
    if task_prefix is None:
        if owner_id is None:
            owner_id = user_id

        user_id = str(user_id)
        task_prefix = user_id + tt + str(owner_id) + tg + str(dc_id)

    x = str(uuid4())

    if dummy:
        return task_prefix + '-' + hashlib.md5(user_id).hexdigest()[-8:] + x[8:-13]

    return task_prefix + '-' + x[:-13]


def task_prefix_from_task_id(task_id):
    """
    Get (user ID, task type, owner ID) tuple from task ID.
    """
    tp = RE_TASK_PREFIX.split(task_id[:-24])
    return tuple(tp + DEFAULT_TASK_PREFIX[len(tp):])


def user_owner_ids_from_task_id(task_id):
    """
    Get user ID and owner ID from task ID.
    """
    task_prefix = task_prefix_from_task_id(task_id)

    return task_prefix[0], task_prefix[2]


def user_owner_dc_ids_from_task_id(task_id):
    """
    Get user ID, owner ID and DC ID from task ID.
    """
    task_prefix = task_prefix_from_task_id(task_id)

    return task_prefix[0], task_prefix[2], task_prefix[4]


def user_id_from_task_id(task_id):
    """
    Get user ID from task ID.
    """
    return user_owner_ids_from_task_id(task_id)[0]


def tt_from_task_id(task_id):
    """
    Get task type from task ID.
    """
    return task_prefix_from_task_id(task_id)[1]


def owner_id_from_task_id(task_id):
    """
    Get owner ID from task ID.
    """
    return task_prefix_from_task_id(task_id)[2]


def tg_from_task_id(task_id):
    """
    Get TG from task ID.
    """
    return task_prefix_from_task_id(task_id)[3]


def dc_id_from_task_id(task_id):
    """
    Get Datacenter ID from task ID.
    """
    return task_prefix_from_task_id(task_id)[4]


def task_id_from_request(request, owner_id=None, dummy=False, tt=TT_EXEC, tg=TG_DC_BOUND, dc_id=DEFAULT_DC):
    """
    Create new task ID from request.
    """
    if isinstance(request, string_types) or isinstance(request, int):
        return task_id_from_string(request, owner_id=owner_id, dummy=dummy, tt=tt, tg=tg, dc_id=dc_id)

    return task_id_from_string(request.user.id, owner_id=owner_id, dummy=dummy, tt=tt, tg=tg, dc_id=request.dc.id)


def task_id_from_task_id(task_id, user_id=None, owner_id=None, tt=None, tg=None, dc_id=None, keep_task_suffix=False):
    """
    Create new task ID with task_prefix taken from existing task ID.
    """
    if user_id or owner_id or tt or tg or dc_id:
        task_prefix = list(task_prefix_from_task_id(task_id))

        if user_id:
            task_prefix[0] = str(user_id)
        if tt:
            task_prefix[1] = tt
        if owner_id:
            task_prefix[2] = str(owner_id)
        if tg:
            task_prefix[3] = tg
        if dc_id:
            task_prefix[4] = str(dc_id)

        task_prefix = ''.join(task_prefix)
    else:
        task_prefix = task_id[:-24]

    if keep_task_suffix:
        return task_prefix + task_id[-24:]

    return task_id_from_string(None, task_prefix=task_prefix)


def generate_internal_task_id():
    """Generate internal task ID"""
    return task_id_from_string(TASK_USER, tt=TT_INTERNAL)


def is_dummy_task(task_id):
    """
    Check if task ID is a real celery task ID.
    """
    # noinspection PyBroadException
    try:
        user_id = user_id_from_task_id(task_id)
        return task_id.split('-')[1] == hashlib.md5(user_id).hexdigest()[-8:]
    except Exception:
        pass

    return False


def is_mgmt_task(task_id):
    """
    Return True if task has task type == 'm'
    """
    return tt_from_task_id(task_id) == TT_MGMT


def is_task_dc_bound(task_id):
    """
    Get dc boundness from task ID.
    """
    return tg_from_task_id(task_id) == TG_DC_BOUND


def _get_ar(ar_or_tid):
    """
    Return AsyncResult.
    """
    if isinstance(ar_or_tid, cq.AsyncResult):
        return ar_or_tid
    else:
        return cq.AsyncResult(ar_or_tid)


def get_result(ar_or_tid):
    """
    Return result (dict) of AsyncResult.

    :returns: AsyncResult.result
    :rtype: dict
    """
    ar = _get_ar(ar_or_tid)
    # noinspection PyBroadException
    try:
        result = ar.result
    except Exception:
        return 'Unknown error'

    if type(result).__name__.endswith('TaskException'):
        # because celery recreates the class TaskException instead of que.tasks.TaskException
        # noinspection PyBroadException
        try:
            result = literal_eval(result.args[0])
        except Exception:
            return 'Unknown failure'

    return result


def follow_callback(ar):
    """
    Check if callback exists and follow it.
    """
    ar = _get_ar(ar)
    # noinspection PyBroadException
    try:
        ar = follow_callback(get_result(ar)['meta']['callback'])
    except Exception:
        pass
    return ar


def get_callback(task_id):
    """
    Check if task has a callback.
    """
    # noinspection PyBroadException
    try:
        return get_result(task_id)['meta']['callback']
    except Exception:
        return False


def is_callback(task_id):
    """
    Check if task is a callback => has a caller.
    """
    # noinspection PyBroadException
    try:
        return get_result(task_id)['meta']['caller']
    except Exception:
        return False


def is_logtask(task_id):
    """
    Check if task is a config.ERIGONES_LOGTASK.
    """
    # noinspection PyBroadException
    try:
        return get_result(task_id)['meta']['cb_name'] == LOGTASK
    except Exception:
        return False


def send_task_forever(sender, task, delay=3, nolog=False, **kwargs):
    """
    Try to run task forever.
    http://docs.celeryproject.org/en/latest/reference/celery.html#celery.Celery.send_task
    """
    ping_check = True
    expires = kwargs.get('expires', None)
    queue = kwargs.get('queue', None)
    max_retries = 1
    num_retries = 0

    while True:
        try:
            if queue and ping_check:
                if not ping(queue):
                    raise PingFailed('Task queue "%s" worker is not responding!' % queue)
            t = cq.send_task(task, **kwargs)
        except Exception as ex:
            logger.warning('Sending task "%s" by %s failed. Error: %s', task, sender, ex)

            if expires:
                if num_retries < max_retries:
                    num_retries += 1
                    logger.warning('Task "%s" sent by %s can expire. Immediate retry attempt %d/%d.', task, sender,
                                   num_retries, max_retries)
                    sleep(1)
                else:
                    logger.error('Task "%s" sent by %s can expire. Failing after %d retries.', task, sender,
                                 num_retries)
                    raise ex
            else:
                num_retries += 1
                worker_shutting_down = E_SHUTDOWN.is_set()

                if worker_shutting_down and num_retries > max_retries:  # We are shutting down and we already tried once
                    ping_check = False  # Just try to send the task without ping check
                    logger.warning('Task "%s" sent by %s must run! Retrying (%d) without ping check...',
                                   task, sender, num_retries)
                    sleep(1)
                else:
                    logger.warning('Task "%s" sent by %s must run! Retrying (%d) in %s seconds...',
                                   task, sender, num_retries, delay)
                    sleep(delay)
        else:
            if nolog:
                logger.debug('Task "%s" with id %s was created by %s', task, t.id, sender)
            else:
                logger.log(IMPORTANT, 'Task "%s" with id %s was created by %s', task, t.id, sender)

            return t


def cancel_task(task_id, terminate=False, signal=None, force=False):
    """
    Revoke task.
    """
    # Callbacks must run; they should never expire (unless you are using force)
    if not force and (get_callback(task_id) or is_callback(task_id)):
        # Parent task has finished
        return False
    # Don't forget that this triggers also signal
    return cq.control.revoke(task_id, terminate=terminate, signal=signal)


def log_task_callback(task_id, task_status=states.REVOKED, cleanup=True, detail='revoked', sender_name='???',
                      send_forever=True):
    """
    Mark task status with task_status and create log callback task. USE with caution!
    """
    user_id, owner_id = user_owner_ids_from_task_id(task_id)

    # Internal user task
    if owner_id == TASK_USER:
        logger.debug('Task %s[%s] %s in log_task_callback :: Internal task - skipping', sender_name, task_id, detail)
        return None

    # If a lock created by this task still exists we need to remove it now - Bug #chili-592
    if cleanup:
        lock_key = TaskLock.get_lock_key_from_value(task_id)

        if lock_key:
            TaskLock(lock_key, desc='LogTask %s' % task_id).delete(check_value=task_id, fail_silently=True)
        else:
            logger.warning('Task %s[%s] %s in log_task_callback :: Reverse lock does not exist',
                           sender_name, task_id, detail)

    # Task info from cache
    task_info = UserTasks(owner_id).get(task_id)

    if task_info is None:
        logger.critical('Task %s[%s] %s in log_task_callback :: Task not found in UserTasks',
                        sender_name, task_id, detail)
        return None

    # Kwargs for logtask
    task_info['task_status'] = task_status
    task_info['cleanup'] = cleanup

    # Create log task on mgmt
    result = {
        'detail': detail,
        'meta': {
            'cb_name': LOGTASK,
            'msg': task_info.get('msg', ''),
            'apiview': task_info.get('apiview', {})
        }
    }

    task_params = {
        'args': (result, task_id),
        'kwargs': task_info,
        'queue': Q_MGMT,
        'expires': None,  # This is callback -> never expire
        'task_id': task_id_from_task_id(task_id),
    }

    if send_forever:
        t = send_task_forever(task_id, LOGTASK, **task_params)
    else:
        t = cq.send_task(LOGTASK, **task_params)

    if t:
        logger.info('Task %s[%s] %s in log_task_callback :: Created logtask %s', sender_name, task_id, detail, t.id)
    else:
        logger.error('Task %s[%s] %s in log_task_callback :: Failed to create logtask', sender_name, task_id, detail)

    return t


def delete_task(task_id, force=False):
    """
    Delete task from UserTasks. Only for tasks which started, but failed to finish and are stuck in DB.
    """

    if force:
        logger.warning('Trying to delete task %s by using force.', task_id)
        logger.warning('Forcing task deletion results in undefined behavior.')
    else:
        return None, 'Safe task deletion is not implemented'

    # The task has a callback, which probably means that it has already finished on compute node.
    callback = get_callback(task_id)
    if callback:
        logger.warning('Task has a callback: %s', callback)

    logger.warning('Going to delete task %s!', task_id)
    # Revoke before proceeding (should not do anything, but won't harm)
    cancel_task(task_id, force=force)

    # So, a task with STARTED state, but is not running and is not a callback (or did not start a callback).
    # In order to delete the task we need to simulate task revoking and create a callback log task for doing a proper
    # cleanup. The log callback will then remove the task from UserTasks.
    try:
        t = log_task_callback(task_id, detail='vanished', send_forever=False)
    except Exception as ex:
        return None, str(ex)

    if t:
        return t.id, None
    else:
        return None, 'Unknown error'


def queue_to_hostnames(queue):
    """
    Return worker hostnames according to queue name.
    """
    if queue == Q_MGMT:
        return cq.conf.ERIGONES_MGMT_WORKERS

    # noinspection PyRedundantParentheses
    return (queue.replace('.', '@', 1),)


def ping(queue, timeout=True, count=1):
    """
    Ping erigonesd worker(s) according to queue and return list of alive workers.
    """
    pong = []
    i = 0
    workers = queue_to_hostnames(queue)

    if isinstance(timeout, bool) and timeout:
        timeout = cq.conf.ERIGONES_PING_TIMEOUT

    while not pong and i < count:
        i += 1

        try:
            res = cq.control.ping(destination=workers, timeout=timeout)
        except Exception as ex:
            logger.warning('Could not ping task queue "%s" workers: %s error: %s', queue, workers, ex)
        else:
            if res:
                for answer in res:
                    worker, status = answer.items()[0]
                    if status == {'ok': 'pong'}:
                        pong.append(worker)
                    else:
                        logger.warning('Ping [%d] of queue "%s" workers "%s" failed (%s)', i, queue, worker, res)
            else:
                logger.warning('Ping [%d] of all queue "%s" workers: %s failed (%s)', i, queue, workers, res)

    return pong


def worker_command(command, destination, **kwargs):
    """
    Synchronous node (celery panel) command.
    """
    kwargs['destination'] = [destination]
    kwargs['reply'] = True

    reply = flatten_reply(cq.control.broadcast(command, **kwargs))

    try:
        return reply[destination]
    except (KeyError, TypeError):
        return None


def validate_uuid(value):
    """
    Validate UUID string.

    Raises ValueError or returns the uuid string if valid.
    """
    return str(UUID(value))  # Will raise ValueError in case of an invalid uuid


def fetch_node_uuid():
    """
    Retrieve node UUID from sysinfo command output.
    """
    proc = Popen(['sysinfo'], bufsize=0, close_fds=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()

    try:
        return validate_uuid(json.loads(stdout)['UUID'])
    except Exception as exc:
        raise NodeError('Could not fetch node UUID: %s' % exc)


def read_file(fp, limit=DEFAULT_FILE_READ_SIZE):
    """
    Return output of fp.read() limited to `limit` bytes of output from the end of file.
    """
    fp.seek(0, 2)  # Go to EOF
    total = fp.tell()

    if total > limit:
        fp.seek(total - limit)
    else:
        fp.seek(0)

    return fp.read()
