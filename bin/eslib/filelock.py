import os
import time
from functools import wraps


class FileLockTimeout(Exception):
    pass


class FileLockError(Exception):
    pass


class FileLock(object):
    """
    Simple file lock.
    """
    def __init__(self, lockfile):
        self._lockfile = lockfile
        self._lockfile_fd = None

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._lockfile)

    def __nonzero__(self):
        return self.is_locked()

    def _write_file(self):
        self._lockfile_fd = os.open(self._lockfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC, 0o644)

    def _remove_file(self):
        os.close(self._lockfile_fd)
        self._lockfile_fd = None
        os.remove(self._lockfile)

    def exists(self):
        return os.path.exists(self._lockfile)

    def is_locked(self):
        return self._lockfile_fd is not None

    def acquire(self, timeout=30, sleep_interval=1):
        start_time = time.time()

        while not self.is_locked():
            if not self.exists():
                try:
                    self._write_file()
                except (OSError, IOError):
                    pass  # Failed to create lock file
                else:
                    break  # Created lock file

            if timeout is not None and (time.time() - start_time) > timeout:
                raise FileLockTimeout('Could not acquire lock within %d seconds' % timeout)
            else:
                time.sleep(sleep_interval)

    def release(self):
        if self.exists():
            if self.is_locked():
                self._remove_file()
            else:
                raise FileLockError('Lock was never acquired')
        else:
            raise FileLockError('Not locked')


def filelock(lockfile, **acquire_kwargs):
    """Simple file lock decorator"""
    def filelock_decorator(fun):
        @wraps(fun)
        def wrap(*args, **kwargs):
            if hasattr(lockfile, '__call__'):
                filepath = lockfile(*args, **kwargs)
            else:
                filepath = lockfile

            flock = FileLock(filepath)
            flock.acquire(**acquire_kwargs)

            try:
                return fun(*args, **kwargs)
            finally:
                flock.release()

        return wrap
    return filelock_decorator
