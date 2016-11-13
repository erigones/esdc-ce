from django.db import models
from django.core.cache import cache
from django.utils.functional import curry


CACHE_MODEL_TIMEOUT = None  # None means never


class CacheManager(models.Manager):
    """
    Like the classic Manager but with get_by_FOO() method(s), which try
    to retrieve the object primary from cache and secondary from DB.
    """
    def __init__(self, cache_fields=()):
        super(CacheManager, self).__init__()
        for i in cache_fields:
            setattr(CacheManager, 'get_by_' + i, curry(CacheManager.__get_by, field=i))

    def __get_by(self, value, field=None, timeout=CACHE_MODEL_TIMEOUT):
        return self._get_by(field, value, timeout)

    def _get_by(self, field, value, timeout=CACHE_MODEL_TIMEOUT):
        key = self.model.cache_key(field, value)

        try:
            res = cache.get(key)
        except (TypeError, ValueError):
            res = None

        if res is None:
            res = self.get(**{field: value})
            cache.set(key, res, timeout)

        return res


class _CacheModel(models.Model):
    """
    Abstract model with CacheManager objects and implicit cache flushing.
    """
    cache_fields = ()
    objects = CacheManager(cache_fields)

    class Meta:
        app_label = 'vms'
        abstract = True

    @classmethod
    def cache_key(cls, field, value):
        return cls.__name__ + '_' + field + ':' + str(value)

    def flush_cache(self):
        for i in self.cache_fields:
            cache.delete(self.cache_key(i, getattr(self, i)))

    def save(self, *args, **kwargs):
        self.flush_cache()
        return super(_CacheModel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.flush_cache()
        return super(_CacheModel, self).delete(*args, **kwargs)
