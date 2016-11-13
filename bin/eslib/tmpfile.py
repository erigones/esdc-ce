import os
import tempfile


class TmpFile(object):
    """
    Create temporary file with context specified as parameter.
    Return the file object.
    """
    _exists = False

    def __init__(self, content, **kwargs):
        fd, self.name = tempfile.mkstemp(**kwargs)
        self._exists = True

        try:
            os.write(fd, content)
            os.close(fd)
        except:
            self.delete()
            raise

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.name)

    def __str__(self):
        return self.name

    def delete(self):
        if self._exists:
            os.remove(self.name)
            self._exists = False

    def __nonzero__(self):
        return self._exists
    __bool__ = __nonzero__

    def __del__(self):
        self.delete()

    def __enter__(self):
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc, value, tb):
        self.delete()
