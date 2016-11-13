from __future__ import absolute_import

from celery import Task, states
from celery.utils.log import get_task_logger

from logging import getLogger

try:
    # noinspection PyPep8Naming
    import cPickle as pickle
except ImportError:
    import pickle

from que import Q_MGMT, TT_MGMT, TG_DC_BOUND
from que.erigonesd import cq
from que.lock import redis_set, NoLock, TaskLock
from que.utils import task_id_from_request, queue_to_hostnames, ping
from que.user_tasks import UserTasks


KEY_PREFIX = cq.conf.ERIGONES_CACHE_PREFIX
EXPIRES = cq.conf.ERIGONES_TASK_DEFAULT_EXPIRES

redis = cq.backend.client
logger = getLogger(__name__)


# noinspection PyAbstractClass
class MgmtTask(Task):
    """
    Abstract task for user tasks running in mgmt queue.
    """
    abstract = True
    logger = None  # Task logger

    def __call__(self, *args, **kwargs):
        self.logger = get_task_logger('que.mgmt')
        task = 'MgmtTask %s%s' % (self.name, args[:2])
        tidlock = kwargs.pop('tidlock', None)
        check_user_tasks = kwargs.pop('check_user_tasks', False)
        kwargs.pop('cache_result', None)
        kwargs.pop('cache_timeout', None)
        kwargs.pop('nolog', None)
        tid = self.request.id

        if tidlock:
            task_lock = TaskLock(tidlock, desc=task, logger=self.logger)
        else:
            task_lock = NoLock()

        try:
            if check_user_tasks:  # Wait for task to appear in UserTasks - bug #chili-618
                UserTasks.check(tid, logger=self.logger)  # Will raise an exception in case the task does not show up

            task_lock.task_check()  # Will raise an exception in case the lock does not exist

            return super(MgmtTask, self).__call__(tid, *args, **kwargs)  # run()
        finally:
            task_lock.delete()

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        task = '%s%s' % (self.name, args[:2])
        self.logger.debug('MgmtTask %s returned %s. Result: """%s"""', task, status, retval)
        cache_result = kwargs.get('cache_result', None)
        cache_timeout = kwargs.get('cache_timeout', None)

        if cache_result and status == states.SUCCESS:
            if redis_set(cache_result, pickle.dumps(retval), cache_timeout):
                self.logger.info('MgmtTask %s saved result in cache "%s"', task, cache_result)
            else:
                self.logger.error('MgmtTask %s did not saved result in cache "%s"', task, cache_result)

    def call(self, request, owner_id, args, kwargs=None, meta=None, tt=TT_MGMT, tg=TG_DC_BOUND,
             tidlock=None, tidlock_timeout=None, cache_result=None, cache_timeout=None, expires=EXPIRES,
             nolog=False, ping_worker=True, check_user_tasks=True):
        """
        Creates task in mgmt queue.
        Returns task_id, error_message and cached_result (if any).
        """
        if kwargs is None:
            kwargs = {}

        if meta is None:
            meta = {}

        tid = task_id_from_request(request, owner_id=owner_id, tt=tt, tg=tg)
        task = 'MgmtTask %s[%s]%s' % (self.name, tid, args[:2])
        tidlock_acquired = False

        if cache_result:
            cache_result = KEY_PREFIX + cache_result + ':cache'
            result = redis.get(cache_result)

            if result is not None:
                try:
                    res = pickle.loads(result)
                except pickle.UnpicklingError:
                    logger.critical('%s could not parse cache_result "%s"', task, cache_result)
                else:
                    return None, None, res

        if ping_worker:
            if not ping(Q_MGMT, timeout=ping_worker, count=2):
                return None, 'Task queue worker (%s) is not responding!' % queue_to_hostnames(Q_MGMT), None

        try:
            if tidlock:
                tidlock = KEY_PREFIX + tidlock + ':lock'
                task_lock = TaskLock(tidlock, desc=task)

                _tid = task_lock.get()
                if _tid:
                    logger.info('%s found the same pending task %s :)', task, _tid)
                    return _tid, None, None

                if tidlock_timeout is None:
                    tidlock_timeout = expires

                tidlock_acquired = task_lock.acquire(tid, timeout=tidlock_timeout)
                if not tidlock_acquired:
                    return None, 'MgmtTask did not acquire lock', None

            kwargs['meta'] = meta
            kwargs['tidlock'] = tidlock
            kwargs['cache_result'] = cache_result
            kwargs['cache_timeout'] = cache_timeout
            kwargs['nolog'] = nolog
            kwargs['check_user_tasks'] = check_user_tasks
            # Run task
            t = self.apply_async(args=args, kwargs=kwargs, queue=Q_MGMT, task_id=tid,
                                 expires=expires, add_to_parent=False)

        except Exception as e:
            logger.exception(e)
            logger.error('%s could not be created (%s)', task, e)

            if tidlock_acquired:  # tidlock_acquired will be True, only if task_lock exists
                # noinspection PyUnboundLocalVariable
                task_lock.delete(fail_silently=True, premature=True)

            return None, e, None

        else:
            if nolog:
                logger.debug('%s created', task)
            else:
                logger.info('%s created', task)

            return t.id, None, None
