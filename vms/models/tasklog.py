from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
# noinspection PyProtectedMember
from django.core.cache import caches

try:
    # noinspection PyPep8Naming
    import cPickle as pickle
except ImportError:
    import pickle

from gui.models import User
from vms.models.dc import Dc

OBJECT_CACHE = {}  # Cache used for one run (is cleared before rendering each tasklog view)
CACHE_KEY_PREFIX = settings.CACHE_KEY_PREFIX

redis = caches['redis'].master_client


class TaskLogEntry(models.Model):
    """
    Task Log.
    """
    cache_pipeline_id = None
    cache_pipeline = None
    cache_object_key = None
    cache_user_key = None

    OTHER = 0
    CREATE = 1
    DELETE = 2
    UPDATE = 3
    REMOTE = 4

    dc = models.ForeignKey(Dc, on_delete=models.CASCADE)
    time = models.DateTimeField(_('time'), db_index=True)
    task = models.CharField(_('task ID'), max_length=64, db_index=True)
    task_type = models.SmallIntegerField(_('task type'), db_index=True, default=0)
    status = models.CharField(_('task status'), max_length=12, db_index=True)
    user_id = models.IntegerField(_('user ID'))
    username = models.CharField(_('username'), max_length=254)
    owner_id = models.IntegerField(_('owner ID'), db_index=True)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE)
    content_type_model = models.CharField(_('object type'), max_length=32, blank=True)
    object_pk = models.CharField(_('object ID'), max_length=128, blank=True, db_index=True)
    object_name = models.CharField(_('object name'), max_length=254, blank=True)
    object_alias = models.CharField(_('object alias'), max_length=254, blank=True)
    flag = models.SmallIntegerField(_('action flag'), default=OTHER)
    msg = models.TextField(_('message'))
    detail = models.TextField(_('detail'), blank=True)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Task Log Entry')
        verbose_name_plural = _('Task Log')
        ordering = ('-time',)

    def __str__(self):
        return '%s (%s)' % (self.id, self.time)

    @staticmethod
    def _cache_set(key, value):
        return redis.set(key, pickle.dumps(value))

    @staticmethod
    def _cache_load(res):
        if res is None:
            return res
        else:
            return pickle.loads(res)

    @classmethod
    def _cache_get(cls, key):
        return cls._cache_load(redis.get(key))

    @staticmethod
    def _cache_delete(key):
        return redis.delete(key)

    @classmethod
    def add(cls, **kwargs):
        """Log!"""
        # Translate object_type to real field name
        kwargs['content_type_model'] = kwargs.pop('object_type', '')
        entry = cls(**kwargs)
        entry.save()

        if entry.flag == cls.UPDATE:
            entry.delete_object_cache()

    @property
    def object_type(self):
        if self.content_type:
            return self.content_type.model
        else:
            return self.content_type_model

    @staticmethod
    def get_object_cache_key(content_type_id, object_pk):
        return '%s:tasklog-entry:%s:%s' % (CACHE_KEY_PREFIX, content_type_id, object_pk)

    @property
    def object_cache_key(self):
        return self.get_object_cache_key(self.content_type_id, self.object_pk)

    @property
    def user_cache_key(self):
        return self.get_object_cache_key(ContentType.objects.get_for_model(User), self.user_id)

    @classmethod
    def save_object_cache(cls, key, obj):
        cls._cache_set(key, obj)

    @classmethod
    def save_user_cache(cls, key, user_obj):
        cls._cache_set(key, user_obj)

    @classmethod
    def clear_object_cache(cls, obj):
        key = cls.get_object_cache_key(ContentType.objects.get_for_model(obj.__class__), obj.pk)
        cls._cache_delete(key)

    def delete_object_cache(self):
        self._cache_delete(self.object_cache_key)

    def push_cache_commands(self, cache_pipeline, cache_id):
        self.cache_pipeline = cache_pipeline
        self.cache_pipeline_id = cache_id
        self.cache_object_key = self.object_cache_key
        self.cache_user_key = self.user_cache_key
        cache_pipeline.get(self.cache_object_key)
        cache_pipeline.get(self.cache_user_key)

    @property
    def cache_pipeline_result(self):
        try:
            return self.cache_pipeline.result
        except AttributeError:
            return []

    def _get_object(self):
        if self.cache_pipeline is None:
            key = self.object_cache_key
            return key, self._cache_get(key)
        else:
            try:
                return self.cache_object_key, self._cache_load(self.cache_pipeline_result[self.cache_pipeline_id])
            except IndexError:
                return self.object_cache_key, None

    def _get_user(self):
        if self.cache_pipeline is None:
            key = self.user_cache_key
            return key, self._cache_get(key)
        else:
            try:
                return self.cache_user_key, self._cache_load(self.cache_pipeline_result[self.cache_pipeline_id + 1])
            except IndexError:
                return self.user_cache_key, None

    def get_object(self):
        """Return current object"""
        if not self.object_pk or not self.content_type:
            return None

        key, obj = self._get_object()

        if obj is None:
            try:
                obj = OBJECT_CACHE[key]
            except KeyError:
                try:
                    # content_type.get_object_for_this_type() is buggy (is not using router for multi-db support)
                    # x = self.content_type.get_object_for_this_type(pk=self.object_pk)
                    # TODO: report to django
                    # noinspection PyProtectedMember
                    _obj = self.content_type.model_class()._base_manager.get(pk=self.object_pk)
                    obj = (_obj.log_name, _obj.log_alias)
                except (ObjectDoesNotExist, AttributeError):
                    obj = ()

                OBJECT_CACHE[key] = obj

            self.save_object_cache(key, obj)

        return obj

    def get_username(self):
        """Return current username"""
        user_key, user_obj = self._get_user()

        if user_obj is None:
            try:
                user_obj = OBJECT_CACHE[user_key]
            except KeyError:
                try:
                    user = User.objects.get(pk=self.user_id)
                    user_obj = (user.log_name, user.log_alias)
                except User.DoesNotExist:
                    user_obj = (self.username, self.username)

                OBJECT_CACHE[user_key] = user_obj

            self.save_user_cache(user_key, user_obj)

        return user_obj[0]
    get_username.short_description = _('username')

    def get_object_name(self):
        """Return current object name"""
        obj = self.get_object()
        if obj:
            return obj[0]
        return self.object_name
    get_object_name.short_description = _('object name')

    def get_object_alias(self):
        """Return current object alias"""
        obj = self.get_object()
        if obj:
            return obj[1]
        return self.object_alias
    get_object_name.short_description = _('object alias')

    @staticmethod
    def prepare_queryset(qs):
        cache_pipe = redis.pipeline()

        for i, item in enumerate(qs):
            item.push_cache_commands(cache_pipe, i * 2)

        cache_pipe.result = cache_pipe.execute()
        OBJECT_CACHE.clear()
