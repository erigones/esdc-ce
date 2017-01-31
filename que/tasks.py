from __future__ import absolute_import

import os
import signal
from logging import getLogger
from subprocess import PIPE
from datetime import datetime
from base64 import b64encode
from zlib import compress

from celery import Task
from celery.exceptions import Terminated
from celery.utils.log import get_task_logger
from celery.signals import celeryd_after_setup, worker_ready, task_revoked
from psutil import Popen, NoSuchProcess

from que import Q_MGMT, TT_EXEC, TG_DC_BOUND, TG_DC_UNBOUND
from que.erigonesd import cq
from que.lock import NoLock, TaskLock
from que.exceptions import TaskRetry
from que.user_tasks import UserTasks
from que.utils import task_id_from_request, task_id_from_task_id, send_task_forever, queue_to_hostnames, ping


LOGTASK = cq.conf.ERIGONES_LOGTASK
EXPIRES = cq.conf.ERIGONES_TASK_DEFAULT_EXPIRES
KEY_PREFIX = cq.conf.ERIGONES_CACHE_PREFIX
MAX_RETRIES = cq.conf.ERIGONES_MAX_RETRIES
RETRY_DELAY = cq.conf.ERIGONES_DEFAULT_RETRY_DELAY
SYSINFO_TASK = cq.conf.ERIGONES_NODE_SYSINFO_TASK

redis = cq.backend.client
logger = getLogger(__name__)


# noinspection PyUnusedLocal
@celeryd_after_setup.connect
def setup_queues(sender, instance, **kwargs):
    if Q_MGMT not in instance.app.amqp.queues:
        from que.handlers import task_revoked_handler
        task_revoked.connect(task_revoked_handler)


# noinspection PyUnusedLocal
@worker_ready.connect
def startup(sender=None, **kwargs):
    if sender:
        from que.handlers import worker_start
        worker_start(sender.hostname)


# noinspection PyAbstractClass
class MetaTask(Task):
    """
    Abstract task for providing meta info and task locking.
    """
    abstract = True
    logger = None  # Task logger
    max_retries = MAX_RETRIES
    default_retry_delay = RETRY_DELAY

    def __call__(self, cmd, *args, **kwargs):
        self.logger = get_task_logger('que.tasks')
        self.all_done = False
        task = 'Task %s("%s")' % (self.name, cmd)
        lock = kwargs.pop('lock', False)
        block = kwargs.pop('block', None)
        check_user_tasks = kwargs.pop('check_user_tasks', False)
        tid = self.request.id
        blocked = False

        if lock:
            task_lock = TaskLock(lock, desc=task, logger=self.logger)
        else:
            task_lock = NoLock()

        try:
            if check_user_tasks:  # Wait for task to appear in UserTasks - bug #chili-618
                UserTasks.check(tid, logger=self.logger)  # Will raise an exception in case the task does not show up

            task_lock.task_check()  # Will raise an exception in case the lock does not exist

            if block and redis.exists(block):
                blocked = True
                self.retry(exc=TaskRetry(None))  # Will raise special exception

            return super(MetaTask, self).__call__(cmd, *args, **kwargs)  # run()
        finally:
            if not blocked:  # Lock must _not_ be deleted when failing on retry
                task_lock.delete()

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        self.logger.debug('Task %s("%s") returned %s. Result: """%s"""', self.name, args, status, retval)
        meta = kwargs.get('meta', {})
        nolog = meta.get('nolog', False)

        # In case of emergency log this task
        if not nolog and not self.all_done:
            if isinstance(retval, dict):
                result = retval.copy()
            else:
                if einfo:
                    result = {'detail': str(einfo.exception)}
                else:
                    result = {'detail': str(retval)}

            if 'meta' not in result:
                result['meta'] = meta

            result['meta']['cb_name'] = LOGTASK
            meta['task_status'] = status
            meta['cleanup'] = True
            t = send_task_forever(task_id, LOGTASK, nolog=nolog, args=(result, task_id), kwargs=meta,
                                  queue=Q_MGMT, expires=None, task_id=task_id_from_task_id(task_id))
            self.logger.warn('Created emergency log task %s', t.id)


def _exc_signal(exc):
    """Try to get signal number from exception"""
    try:
        sig = int(str(exc))
    except (ValueError, TypeError):
        sig = signal.SIGTERM

    return sig


@cq.task(name='que.tasks.execute', base=MetaTask, bind=True)
def _execute(self, cmd, stdin, meta=None, callback=None):
    """
    The "real" execute function.
    Just like executing a command in the shell on the compute node.
    Do not use directly. Call the execute() wrapper instead.
    """
    request = self.request

    p = Popen(cmd, shell=True, bufsize=0, close_fds=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, preexec_fn=os.setsid)
    exec_time = datetime.utcnow()

    try:
        stdout, stderr = p.communicate(input=stdin)
    except (Terminated, KeyboardInterrupt, SystemExit) as exc:
        # This is mainly used for fetching SIGTERM
        # The SIGTERM signal will be caught here as Terminated exception and the SIGKILL will never be caught here.
        sig = _exc_signal(exc)
        logger.error('Task %s received %r exception -> sending signal %d to %d', request.id, exc, sig, p.pid)

        try:
            os.killpg(p.pid, sig)  # Send signal to process group
        except OSError:
            pass

        try:
            p.send_signal(sig)  # Send signal to process and wait
            p.wait()
        except (OSError, NoSuchProcess):
            pass

        raise exc

    finish_time = datetime.utcnow()

    if meta is None:
        meta = {}

    elif meta:
        if 'replace_text' in meta:
            for i in meta['replace_text']:
                stdout = stdout.replace(i[0], i[1])
                stderr = stderr.replace(i[0], i[1])
            del meta['replace_text']

        if 'replace_stdout' in meta:
            for i in meta['replace_stdout']:
                stdout = stdout.replace(i[0], i[1])
            del meta['replace_stdout']

        if 'replace_stderr' in meta:
            for i in meta['replace_stderr']:
                stderr = stderr.replace(i[0], i[1])
            del meta['replace_stderr']

        if 'compress_stdout' in meta:
            stdout = compress(stdout)
            del meta['compress_stdout']

        if 'compress_stderr' in meta:
            stderr = compress(stderr)
            del meta['compress_stderr']

        if 'encode_stdout' in meta:
            stdout = b64encode(stdout)
            del meta['encode_stdout']

        if 'encode_stderr' in meta:
            stderr = b64encode(stderr)
            del meta['encode_stderr']

    meta['exec_time'] = exec_time.isoformat()
    meta['finish_time'] = finish_time.isoformat()

    if 'output' in meta:
        result = meta.pop('output', {})
        result['meta'] = meta

        _stdout = result.pop('stdout', None)
        if _stdout:
            result[_stdout] = stdout.strip()

        _stderr = result.pop('stderr', None)
        if _stderr:
            result[_stderr] = stderr.strip()

        _returncode = result.pop('returncode', None)
        if _returncode:
            result[_returncode] = p.returncode

    else:
        result = {
            'returncode': p.returncode,
            'stdout': stdout,
            'stderr': stderr,
            'meta': meta,
        }

    # Implicit logging if no callback is specified
    # Use callback=False to disable automatic logging
    if callback is None:
        callback = [LOGTASK, meta, None]

    if callback:
        nolog = meta.get('nolog', False)
        cb_name = callback[0]
        cb_kwargs = {}
        cb_expire = None

        if len(callback) > 1:
            cb_kwargs = callback[1]
            if len(callback) > 2:
                cb_expire = callback[2]

        t = send_task_forever(request.id, cb_name, nolog=nolog, args=(result, request.id), kwargs=cb_kwargs,
                              queue=Q_MGMT, expires=cb_expire, task_id=task_id_from_task_id(request.id))
        result['meta']['cb_name'] = cb_name
        result['meta']['callback'] = t.id

    # Do not run emergency callback in after_return
    self.all_done = True

    return result


def execute(request, owner_id, cmd, stdin=None, meta=None, callback=None, lock=None, lock_timeout=None, queue=None,
            expires=EXPIRES, tt=TT_EXEC, tg=TG_DC_BOUND, nolog=False, ping_worker=True,
            check_user_tasks=True, block_key=None):
    """
    _execute task wrapper. This just looks better and does some locking.
    Returns task_id and error_message
    """
    task_id = task_id_from_request(request, owner_id=owner_id, tt=tt, tg=tg)
    task = 'Task %s[%s]("%s")' % (_execute.name, task_id, cmd)
    lock_key = lock
    lock_acquired = False

    if meta is None:
        meta = {}

    if ping_worker and queue:
        # callback=None means, that an automatic log task callback will run
        if callback is not False and queue != Q_MGMT:
            queues = [queue, Q_MGMT]
        else:
            queues = [queue]

        for q in queues:
            if not ping(q, timeout=ping_worker, count=2):
                return None, 'Task queue worker (%s) is not responding!' % queue_to_hostnames(q)

    try:
        if lock_key:
            if lock_timeout is None:
                lock_timeout = expires

            lock_key = KEY_PREFIX + lock
            task_lock = TaskLock(lock_key, desc=task)
            lock_acquired = task_lock.acquire(task_id, timeout=lock_timeout)

            if not lock_acquired:
                return task_id, 'Task did not acquire lock'

        meta['nolog'] = nolog
        args = (cmd, stdin)
        kwargs = {'meta': meta, 'callback': callback, 'lock': lock_key, 'block': block_key,
                  'check_user_tasks': check_user_tasks}
        # Run task
        task = _execute.apply_async(args=args, kwargs=kwargs, queue=queue, task_id=task_id,
                                    expires=expires, add_to_parent=False)

    except Exception as e:
        logger.exception(e)
        logger.error('%s could not be created (%s)', task, e)

        if lock_acquired:  # lock_acquired will be True, only if task_lock exists
            # noinspection PyUnboundLocalVariable
            task_lock.delete(fail_silently=True, premature=True)

        return None, e

    else:
        if nolog:
            logger.debug('%s created', task)
        else:
            logger.info('%s created', task)

        return task.id, None


def execute_sysinfo(request, owner_id, queue, node_uuid, meta=None, check_user_tasks=False, initial=False):
    """
    Wrapper around the execute() function calling command esysinfo on a node.

    :param request: REST API request object holding
    :type request: :class:api.request.Request or str/int (user ID)
    :param owner_id: ID of the owner of the task
    :type owner_id: str or int
    :param queue: Celery queue into which the task should be placed
    :type queue: str
    :param node_uuid: UUID of the node on which sysinfo should be executed
    :type node_uuid: str
    :param meta: Meta information needed to track the task in queue
    :type meta: dict
    :param check_user_tasks: Waiting for task to appear in UserTasks
    :type check_user_tasks: bool
    :param initial: Whether the esysinfo command is run during first start of erigonesd:fast
    :type initial: bool

    :return: tuple (task_id, error) i.e. same values as execute() function
    """
    if initial:
        esysinfo_cmd = 'esysinfo init 2> /dev/null'
    else:
        esysinfo_cmd = 'esysinfo 2> /dev/null'

    lock = 'node_sysinfo node_queue:%s' % queue
    callback = (SYSINFO_TASK, {'node_uuid': node_uuid})

    return execute(request, owner_id, cmd=esysinfo_cmd, lock=lock, meta=meta,
                   callback=callback, queue=queue, tt=TT_EXEC, tg=TG_DC_UNBOUND,
                   ping_worker=False, check_user_tasks=check_user_tasks)
