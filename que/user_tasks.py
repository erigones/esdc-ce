from __future__ import absolute_import

from logging import getLogger
from time import sleep
from six import iteritems

try:
    # noinspection PyPep8Naming
    import cPickle as pickle
except ImportError:
    import pickle

from que.erigonesd import cq
from que.exceptions import UserTaskError


KEY_PREFIX = cq.conf.ERIGONES_CACHE_PREFIX
CHECK_TIMEOUT = cq.conf.ERIGONES_CHECK_USER_TASK_TIMEOUT

logger = getLogger(__name__)


class UserTasks(object):
    """
    User tasks dict (with task_id as keys) stored in cache.
    """
    redis = cq.backend.client
    key_all = KEY_PREFIX + 'tasks'

    __slots__ = ('user_id', 'key', 'data')

    def __init__(self, user_id):
        """Save the cache key."""
        self.user_id = user_id
        self.key = KEY_PREFIX + 'tasks-' + str(user_id)
        self.data = {}

    def __repr__(self):
        return '<User: %s, Tasks: %s>' % (self.user_id, self.data.keys())

    @classmethod
    def exists(cls, task_id):
        """Return boolean indicating if task is registered in running tasks list."""
        return cls.redis.sismember(cls.key_all, task_id)

    # noinspection PyShadowingNames
    @classmethod
    def check(cls, task_id, timeout=CHECK_TIMEOUT, logger=logger):
        """Check and wait for user task to appear in user's task list"""
        wait = 0.5

        while True:
            if cls.exists(task_id):
                logger.info('Task "%s" was found in UserTasks', task_id)
                break

            if wait > timeout:
                logger.error('Ou ou. Task "%s" was not registered in UserTasks. Failing after waiting for %s seconds.',
                             task_id, wait)
                raise UserTaskError('Task "%s" was not registered in user\'s task list' % task_id)

            if wait > 1:
                logger.warn('Whoa! Task "%s" not found in UserTasks. Waiting for %s seconds', task_id, wait)
            else:
                logger.info('Whoa! Task "%s" not found in UserTasks. Waiting for %s seconds', task_id, wait)

            sleep(wait)
            wait *= 2

    @property
    def tasks(self):
        return self.load()

    @property
    def tasklist(self):
        return self.redis.hkeys(self.key)

    @property
    def tasklist_all(self):
        return self.redis.smembers(self.key_all)

    def load(self):
        """Load pending user tasks from cache."""
        self.data.clear()

        for task_id, task_info in iteritems(self.redis.hgetall(self.key)):
            self.data[task_id] = pickle.loads(task_info)

        return self.data

    def get(self, task_id):
        """Get task from dict of running user tasks."""
        task_info = self.redis.hget(self.key, task_id)

        if task_info is not None:
            return pickle.loads(task_info)

        return None

    def add(self, task_id, task_info):
        """Add task to dict of running user tasks."""
        ar = cq.AsyncResult(task_id)

        if ar.ready():  # Double-check if task is still in PENDING or STARTED state
            raise UserTaskError('Task "%s" cannot be registered in user\'s task list '
                                'because it has already finished' % task_id)

        pipe = self.redis.pipeline()
        pipe.hset(self.key, task_id, pickle.dumps(task_info))
        pipe.sadd(self.key_all, task_id)
        res = bool(pipe.execute()[0])

        if res:
            logger.info('Task %s added into %s', task_id, self.key)
        else:
            logger.warn('Task %s was updated in %s', task_id, self.key)

        return res

    def delete(self, task_id):
        """Delete task from dict of running user tasks."""
        pipe = self.redis.pipeline()
        pipe.hdel(self.key, task_id)
        pipe.srem(self.key_all, task_id)
        res = bool(pipe.execute()[0])

        if res:
            logger.info('Task %s removed from %s', task_id, self.key)
        else:
            logger.warn('Task %s was not removed from %s', task_id, self.key)

        return res

    def pop(self, task_id):
        """Delete task from dict of running user tasks and return task_info."""
        task_info = self.get(task_id)

        if task_info is None:
            return {}

        self.delete(task_id)

        return task_info
