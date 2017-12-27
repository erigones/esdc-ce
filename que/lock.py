from logging import getLogger

from que.erigonesd import cq
from que.exceptions import TaskLockError

redis = cq.backend.client
logger = getLogger(__name__)

KEY_PREFIX = cq.conf.ERIGONES_CACHE_PREFIX


def redis_set(key, value, timeout=None, nx=False):
    # TODO: This code will be deprecated soon (related to redis 2.6 upgrade)
    pipe = redis.pipeline()

    if nx:
        pipe.setnx(key, value)
    else:
        pipe.set(key, value)

    if timeout:
        pipe.expire(key, int(timeout))

    return pipe.execute()[0]


class NoLock(object):
    """
    Dummy class that silently eats up everything and does nothing.
    """
    def __nonzero__(self):
        return False
    __bool__ = __nonzero__

    # noinspection PyUnusedLocal
    def __getattr__(self, item):
        return lambda *args, **kwargs: None


class TaskLock(object):
    """
    Task lock used by execute task and MgmtTask. Use task ID as the lock value.
    """
    __slots__ = ('key', 'reverse_key', 'desc', 'log')

    # noinspection PyShadowingNames
    def __init__(self, name, desc='Task', reverse_key=None, logger=logger):
        # Lock name - the cache key must come with the prefix already set
        self.key = name

        if reverse_key:
            self.reverse_key = self._get_reverse_key(reverse_key)
        else:
            # We don't know if are going to need the reverse_key yet
            self.reverse_key = None

        # Description for logging purposes
        self.desc = desc
        # Set logger
        self.log = logger

    @staticmethod
    def _get_reverse_key(lock_value):
        """Get reverse relation lock key"""
        return '%s%s:lock' % (KEY_PREFIX, lock_value)

    @classmethod
    def get_lock_key_from_value(cls, lock_value):
        """Get original lock key from lock value (probably task_id)"""
        return redis.get(cls._get_reverse_key(lock_value))

    def _reverse_key(self, lock_value):
        """Generate reverse key and save it"""
        if self.reverse_key is None:
            self.reverse_key = self._get_reverse_key(lock_value)

        return self.reverse_key

    def _set_reverse(self, lock_value, timeout=None):
        """Store reverse relation: lock value -> lock key - always fail silently"""
        # noinspection PyNoneFunctionAssignment
        rkey = self._reverse_key(lock_value)

        try:
            if redis_set(rkey, self.key, timeout=timeout):
                self.log.info('%s saved reverse lock: "%s" with timeout=%ss', self.desc, rkey, timeout)
            else:
                self.log.warning('%s could not save reverse lock: "%s"', self.desc, rkey)
        except Exception as e:
            logger.exception(e)

    def _delete_reverse(self, lock_value):
        """Delete reverse relation for lock value - always fail silently"""
        # noinspection PyNoneFunctionAssignment
        rkey = self._reverse_key(lock_value)

        try:
            if redis.delete(rkey):
                self.log.info('%s removed reverse lock: "%s"', self.desc, rkey)
            else:
                self.log.warning('%s could not remove reverse lock: "%s"', self.desc, rkey)
        except Exception as e:
            logger.exception(e)

    def acquire(self, value, timeout=None, save_reverse=True):
        """Try to acquire lock and return boolean success value"""
        if not timeout:
            self.log.warning('%s has no timeout set!', self.desc)

        res = redis_set(self.key, value, timeout=timeout, nx=True)

        if res:
            self.log.info('%s acquired lock: "%s" with timeout=%ss', self.desc, self.key, timeout)

            if save_reverse:
                self._set_reverse(value, timeout=timeout)

        else:
            self.log.warning('%s could not acquire lock: "%s"', self.desc, self.key)

        return res

    def delete(self, check_value=None, fail_silently=False, premature=False, delete_reverse=True):
        """Try to delete lock and return boolean success value"""
        if premature:
            lock = '*premature* lock: "%s"' % self.key
            log = self.log.warning
        else:
            lock = 'lock: "%s"' % self.key
            log = self.log.info

        try:
            value = redis.get(self.key)

            if check_value is not None and check_value != value:
                self.log.warning('%s did not release %s, because lock values did not match ("%s" != "%s")',
                                 self.desc, lock, check_value, value)
                return False

            res = bool(redis.delete(self.key))
        except Exception as e:
            if fail_silently:
                self.log.exception(e)
                return False
            else:
                raise e

        if res:
            log('%s released %s', self.desc, lock)

            if delete_reverse:
                self._delete_reverse(value)  # Always fails silently (will not produce any exception)

        else:
            self.log.error('%s could not release %s', self.desc, lock)

        return res

    def exists(self):
        """Return boolean value indicating existence of lock file"""
        return redis.exists(self.key)
    acquired = exists

    def get(self):
        """Return lock value"""
        return redis.get(self.key)
    check = get

    def task_check(self, errmsg='Task did not acquire lock'):
        """Check performed by MetaTask and MgmtTask when the task is already running"""
        if self.exists():
            self.log.info('%s has acquired lock: "%s" -> removing lock expiration!', self.desc, self.key)
            redis.persist(self.key)

            if self.reverse_key:
                self.log.info('%s has reverse lock: "%s" -> removing reverse lock expiration!',
                              self.desc, self.reverse_key)
                redis.persist(self.reverse_key)
        else:
            self.log.error('%s did not acquire lock: "%s"', self.desc, self.key)
            raise TaskLockError(errmsg)
