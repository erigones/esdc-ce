import re

from django.db import models, transaction
from django.utils import timezone
from django.utils.six import iteritems, with_metaclass
from django.utils.translation import ugettext_lazy as _
from django.core.cache import cache
from django.core.exceptions import SuspiciousOperation
from django.contrib.contenttypes.models import ContentType
from django_celery_beat.models import PeriodicTask, CrontabSchedule

import base64
import copy
import pickle

from vms.utils import PickleDict, RWMethods
from gui.models import User
from que.utils import owner_id_from_task_id
from que.user_tasks import UserTasks


class _DummyModelBase(type):
    def __new__(mcs, name, bases, attrs):
        meta = attrs.pop('Meta', None)
        new_class = type.__new__(mcs, name, bases, attrs)

        if meta:
            meta.model_name = name.lower()
            meta.concrete_model = new_class
            setattr(new_class, '_meta', meta)
        else:
            raise AttributeError('Class %s has no "class Meta" definition' % name)

        return new_class


class _DummyModel(with_metaclass(_DummyModelBase)):
    """
    Dummy model simulating some properties of django models
    """
    _pk_key = NotImplemented

    class Meta:
        pass


class _DummyDataModel(with_metaclass(_DummyModelBase)):
    """
    Dummy model simulating some properties of django models + serialization of internal data dictionary.
    """
    class Meta:
        pass

    def __new__(cls, *args, **kwargs):
        # noinspection PyArgumentList
        obj = super().__new__(cls)
        obj._data = {}
        return obj

    def __init__(self, data=None):
        if data:
            self._data.update(data)

    def __getattr__(self, key):
        if key.startswith('_'):
            # noinspection PyUnresolvedReferences
            return super().__getattr__(key)
        else:
            return self._data[key]

    def __setattr__(self, key, value):
        if key.startswith('_'):
            return super().__setattr__(key, value)
        else:
            self._data[key] = value

    def __delattr__(self, key):
        if key.startswith('_'):
            return super().__delattr__(key)
        else:
            return self._data.__delitem__(key)

    def __getstate__(self):
        return self._data.copy()

    def __setstate__(self, state):
        self._data = state

    def __iter__(self):
        return iteritems(self._data)

    def __getitem__(self, item):
        return self._data.__getitem__(item)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def update(self, data):
        self._data.update(data)


class _PickleModel(models.Model):
    """
    Abstract class with pickle encoding and decoding of field attributes.
    """
    class Meta:
        app_label = 'vms'
        abstract = True

    @staticmethod
    def _decode(xdata):
        """Unpickle data from DB and return a PickleDict object"""
        # xdata are stored as string
        # Python2 pickle loads accepts string and b64decode accepts both string and bytes and return string
        # Python3 pickle loads accepts bytes and b64decode accepts both string and bytes and return bytes
        # Pickle loads detects version of pickle automaticaly: Python2 default version 2, Python3 default version 3 or 4
        data = pickle.loads(base64.b64decode(xdata))
        if not isinstance(data, PickleDict):
            data = PickleDict(data)
        return data

    @staticmethod
    def _encode(xdata):
        """Pickle a dict object and return data, which can be saved in DB"""
        if not isinstance(xdata, dict):
            raise ValueError('json is not a dict')
        # Python2 pickle.dumps returns string, and also b64encode returned string (accepts both bytes and string)
        # Python3 pickle.dumps returns bytes, and also b64encode returned bytes (accepts ONLY bytes)
        # Make it compatible with OLD data stored in DB (a.k.a. string) so convert to string!
        return base64.b64encode(pickle.dumps(copy.copy(dict(xdata)))).decode('utf8')


class _JsonPickleModel(_PickleModel):
    """
    Abstract _PickleModel with json attributes stored in enc_json field.
    """
    EMPTY = 'KGRwMQou\n'

    class Meta:
        app_label = 'vms'
        abstract = True

    # don't access 'encoded_data' directly, use the 'data' property instead, etc
    # default is an empty dict
    enc_json = models.TextField(blank=False, editable=False, default=EMPTY)

    # Access the json property to load/save/manipulate the dict object
    # json is the dict which will be used for creating/updating the VM on SmartOS
    @property
    def json(self):
        return self._decode(self.enc_json)

    @json.setter
    def json(self, data):
        self.enc_json = self._encode(data)

    def save_item(self, key, value, save=True, metadata=None, **kwargs):
        """Set one item in json"""
        _json = self.json

        if metadata:
            if metadata not in _json:
                _json[metadata] = {}
            _json[metadata][key] = value
        else:
            _json[key] = value

        self.json = _json

        if save:
            return self.save(**kwargs)
        else:
            return True

    def save_items(self, save=True, metadata=None, **key_value):
        """Save multiple items in json"""
        _json = self.json

        if metadata:
            if metadata not in _json:
                _json[metadata] = {}
            _json[metadata].update(key_value)
        else:
            _json.update(key_value)

        self.json = _json

        if save:
            return self.save()
        else:
            return True

    def delete_item(self, key, save=True, metadata=None, **kwargs):
        """Set one item in json"""
        _json = self.json

        try:
            if metadata:
                if metadata in _json:
                    del _json[metadata][key]
            else:
                del _json[key]
        except KeyError:
            pass

        self.json = _json

        if save:
            return self.save(**kwargs)
        else:
            return True


class _StatusModel(models.Model):
    """
    Abstract model class with basic status attributes.
    Also tracks changes of status property and updates the status_change
    attribute if changed. Status information is cached - the key is PK:status.
    """
    _lock = False  # Cannot be saved when True
    _cache_status = False  # Should we cache the status into redis after calling save()?
    _orig_status = None  # Original value of status
    _update_changed = True  # When True, the changed field will be updated at each save()
    # status = models.SmallIntegerField(_('Status'))  # You need this in descendant
    status_change = models.DateTimeField(_('Last status change'), default=None, null=True, editable=False)
    created = models.DateTimeField(_('Created'), editable=False)
    changed = models.DateTimeField(_('Last changed'), editable=False)

    class Meta:
        app_label = 'vms'
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_status = self.status

    @staticmethod
    def status_key(pk):  # public helper for accessing the cache key
        return str(pk) + ':status'

    @staticmethod
    def status_change_key(pk):  # public helper for accessing the cache key
        return str(pk) + ':status-change'

    @property  # just a helper, so we have one method to construct the cache key
    def obj_status_key(self):
        return _StatusModel.status_key(self.pk)

    @property  # just a helper, so we have one method to construct the cache key
    def obj_status_change_key(self):
        return _StatusModel.status_change_key(self.pk)

    def lock(self):
        self._lock = True

    def unlock(self):
        self._lock = False

    def save(self, *args, **kwargs):
        """Update status_change and cache when needed"""
        if self._lock:  # Used for active json display in vm_define when the json is overwritten by active json
            raise SuspiciousOperation('%s object "%s" is locked!' % (self.__class__.__name__, self))

        now = timezone.now()
        status_change_time = kwargs.pop('status_change_time', now)
        update_fields = kwargs.get('update_fields', None)

        if self._update_changed:
            self.changed = now

        if not self.created:
            self.created = now
        if self.status != self._orig_status:
            self.status_change = status_change_time

        res = super().save(*args, **kwargs)

        # update cache if status changed
        if self.status != self._orig_status and (update_fields is None or 'status' in update_fields):
            if self._cache_status:
                cache.set(self.obj_status_key, self.status)
                cache.set(self.obj_status_change_key, self.status_change)
            self._orig_status = self.status

        return res

    def save_status(self, new_status=None, **kwargs):
        """Just update the status field (and other related fields)"""
        if new_status is not None:
            self.status = new_status

        return self.save(update_fields=('status', 'status_change'), **kwargs)

    # noinspection PyUnusedLocal
    @staticmethod
    def post_delete_status(sender, instance, **kwargs):
        """Clean cache after removing the object - call from signal"""
        # noinspection PyProtectedMember
        if instance._cache_status:  # remove the cache entries
            cache.delete(instance.obj_status_key)
            cache.delete(instance.obj_status_change_key)


class _OSType(models.Model):
    """
    Abstract class used for children to inherit OS type attributes and field.
    """
    LINUX = 1
    SUNOS = 2
    BSD = 3
    WINDOWS = 4
    SUNOS_ZONE = 5
    LINUX_ZONE = 6

    OSTYPE = (
        (LINUX, _('Linux VM')),
        (SUNOS, _('SunOS VM')),
        (BSD, _('BSD VM')),
        (WINDOWS, _('Windows VM')),
        (SUNOS_ZONE, _('SunOS Zone')),
        (LINUX_ZONE, _('Linux Zone')),
    )

    # KVM = frozenset([LINUX, SUNOS, BSD, WINDOWS])   # to HVM
    HVM_OSTYPES = frozenset([LINUX, SUNOS, BSD, WINDOWS])
    ZONE_OSTYPES = frozenset([SUNOS_ZONE, LINUX_ZONE])

    class Meta:
        app_label = 'vms'
        abstract = True

    # ostype = models.SmallIntegerField(_('Guest OS type'), choices=OSTYPE)


class _HVMType(models.Model):
    """
    Abstract class used for children to inherit hvm_type attributes and field.
    """

    Hypervisor_KVM = 1
    Hypervisor_BHYVE = 2
    Hypervisor_NONE = 3    # for zones

    HVM_TYPE = (
        (Hypervisor_KVM, _('KVM hypervisor')),
        (Hypervisor_BHYVE, _('BHYVE hypervisor')),
        (Hypervisor_NONE, _('NO hypervisor')),
    )

    # used on VM create or when editing HVM VM
    HVM_TYPE_GUI = (
        (Hypervisor_KVM, _('KVM')),
        (Hypervisor_BHYVE, _('BHYVE')),
    )

    # used in VM modal when editing already created zone
    HVM_TYPE_GUI_NO_HYPERVISOR = (
        (Hypervisor_NONE, _('NO hypervisor')),
    )

    HVM = frozenset([Hypervisor_KVM, Hypervisor_BHYVE])

    class Meta:
        app_label = 'vms'
        abstract = True


class _VirtModel(models.Model):
    """
    Abstract class used by any virtualization object/bucket, like Image and
    Network. All this objects should have this common attributes for unified
    access and naming strategy.

    Example: Image access strategy
    ------------------------------
    Public: Customers can purchase this image
    Disabled: Shown to customers, but they are not able to purchase it
    Private: Internal images shown only to image owners
    Deleted: Do not show to anybody
    """
    PUBLIC = 1
    DISABLED = 2
    PRIVATE = 3
    DELETED = 4
    INTERNAL = 9
    ACCESS = (
        (PUBLIC, _('Public')),
        (DISABLED, _('Disabled')),
        (PRIVATE, _('Private')),
        (DELETED, _('Deleted')),
        (INTERNAL, _('Internal')),
    )

    INVISIBLE = (DELETED, INTERNAL)
    UNUSABLE = (DISABLED, DELETED, INTERNAL)

    name = models.CharField(_('Name'), max_length=64, unique=True)
    alias = models.CharField(_('Alias'), max_length=32)
    desc = models.CharField(_('Description'), max_length=128, blank=True)
    owner = models.ForeignKey(User, verbose_name=_('Owner'), on_delete=models.PROTECT)
    access = models.SmallIntegerField(_('Access'), choices=ACCESS, default=PRIVATE)
    created = models.DateTimeField(_('Created'), auto_now_add=True, editable=False)
    changed = models.DateTimeField(_('Last changed'), auto_now=True, editable=False)

    class Meta:
        app_label = 'vms'
        abstract = True
        # unique_together = (('alias', 'owner'),)
        # ^^^^ This is very important and should be placed in the descendant model.

    def __str__(self):
        return '%s' % self.name


class _UserTasksModel(object):
    """
    Model for working (listing, adding, removing) with user tasks related to this object.

    WARNING: this implementation depends on the owner attribute.
    Object owner must _not_ change when a pending task exists!
    """
    owner = None  # This class is only useful in models that have a owner attribute
    pk = NotImplemented  # Should always exist in any django model
    _pk_key = NotImplemented  # Set in descendant class
    _log_name_attr = 'name'  # Name of object's attribute which will be used for the object_name field in TaskLogEntry

    class Meta:
        app_label = 'vms'
        abstract = True

    @staticmethod
    def _add_task(user_id, task_id, info):
        return UserTasks(user_id).add(task_id, info)

    @staticmethod
    def _pop_task(user_id, task_id):
        return UserTasks(user_id).pop(task_id)

    @staticmethod
    def _get_tasks(user_id):
        return UserTasks(user_id).tasks

    # noinspection PyMethodMayBeStatic
    def default_apiview(self):
        """Return dict with object related attributes which are always available in apiview"""
        return {}

    def get_tasks(self, match_dict=None):
        """Return pending tasks for this VM as a dict with task_id as keys.
        If match_dict is specified then try to match key/values to current
        tasks and if task is found return only the one task else return {}."""
        res = {}

        for tid, task in iteritems(self._get_tasks(self.owner.id)):
            if task.get(self._pk_key, None) == self.pk:
                res[tid] = task.get('apiview', {})

        if match_dict:
            subtasks = {}

            for tid, task in iteritems(res):
                match_found = all(task.get(k, None) == v for k, v in iteritems(match_dict))

                if match_found:
                    subtasks[tid] = task

            return subtasks

        return res

    @property  # property to get_tasks() method
    def tasks(self):
        return self.get_tasks()

    @property
    def tasks_rw(self):
        return self.get_tasks(match_dict={'method': RWMethods})

    def tasks_ro(self):
        return self.get_tasks(match_dict={'method': 'GET'})

    @classmethod
    def _create_task_info(cls, pk, apiview, msg, additional_apiview=None):
        """Prepare task info dict (will be stored in UserTasks cache)"""
        if apiview is None:
            apiview = {}

        if additional_apiview:
            apiview.update(additional_apiview)

        if 'time' not in apiview:
            apiview['time'] = timezone.now().isoformat()

        return {cls._pk_key: pk, 'msg': msg, 'apiview': apiview}

    @classmethod
    def _tasks_add(cls, pk, task_id, apiview, msg='', **additional_apiview):
        """Add task to pending tasks dict in cache."""
        info = cls._create_task_info(pk, apiview, msg, additional_apiview=additional_apiview)

        return cls._add_task(owner_id_from_task_id(task_id), task_id, info)

    def tasks_add(self, task_id, apiview, msg='', **additional_apiview):
        """Add task to pending tasks dict in cache."""
        return self._tasks_add(self.pk, task_id, apiview, msg=msg, **additional_apiview)

    @classmethod
    def _tasks_del(cls, task_id, apiview=None, **additional_apiview):
        """Delete task from pending tasks dict in cache."""
        if apiview is None:
            info = cls._pop_task(owner_id_from_task_id(task_id), task_id)
            apiview = info.get('apiview', {})

        if additional_apiview:
            apiview.update(additional_apiview)

        # Store task info for socket.io que monitor
        cache.set('sio-' + task_id, apiview, 60)

        return apiview

    def tasks_del(self, task_id, **additional_apiview):
        """Delete task from pending tasks dict in cache."""
        info = self._pop_task(owner_id_from_task_id(task_id), task_id)
        apiview = info.get('apiview', {})
        apiview.update(self.default_apiview())

        return self._tasks_del(task_id, apiview=apiview, **additional_apiview)

    @classmethod
    def get_log_name_lookup_kwargs(cls, log_name_value):
        """Return lookup_key=value DB pairs which can be used for retrieving objects by log_name value"""
        return {cls._log_name_attr: log_name_value}

    @classmethod
    def get_content_type(cls):
        # Warning: get_content_type will be deprecated soon. New models should implement get_object_type()
        return ContentType.objects.get_for_model(cls)

    @classmethod
    def get_object_type(cls, content_type=None):
        if content_type:
            return content_type.model
        return cls.get_content_type().model

    @classmethod
    def get_object_by_pk(cls, pk):
        # noinspection PyUnresolvedReferences
        return cls.objects.get(pk=pk)

    @classmethod
    def get_pk_key(cls):
        return cls._pk_key

    @property
    def log_name(self):
        return getattr(self, self._log_name_attr)

    @property
    def log_alias(self):
        # noinspection PyUnresolvedReferences
        return self.alias

    @property
    def log_list(self):
        return self.log_name, self.log_alias, self.pk, self.__class__


class _VmDiskModel(models.Model):
    """
    Abstract class with Virtual Machine disk_id and array_disk_id fields.
    """
    _vm_disk_map = None  # Cached real_disk_id -> disk_id mapping
    _vm_disks = None  # Cache vm.json_active_get_disks()
    vm = None  # declare in descendant class
    disk_id = models.SmallIntegerField(_('Disk ID'))  # Always store real_disk_id

    class Meta:
        app_label = 'vms'
        abstract = True

    def get_disk_map(self):
        """Return real_disk_id -> disk_id mapping"""
        self._vm_disks = self.vm.json_active_get_disks()
        return self.vm.get_disk_map(self._vm_disks)

    @property  # Fake disk_id
    def array_disk_id(self):
        if self._vm_disk_map is None:
            self._vm_disk_map = self.get_disk_map()

        return self._vm_disk_map[self.disk_id] + 1

    @property
    def disk_size(self):
        disk_id = self.array_disk_id - 1
        return self._vm_disks[disk_id]['size']

    @property
    def zfs_filesystem(self):
        disk_id = self.array_disk_id - 1
        return self._vm_disks[disk_id]['zfs_filesystem']

    @staticmethod
    def get_real_disk_id(disk_or_path):
        """Return integer disk suffix from json.disks.*.path attribute"""
        if isinstance(disk_or_path, dict):
            disk_path = disk_or_path['path']
        else:
            disk_path = disk_or_path

        return int(re.split('-|/', disk_path)[-1].lstrip('disk'))

    @classmethod
    def get_disk_id(cls, vm, array_disk_id):
        """Return real_disk_id from vm's active_json"""
        disk = vm.json_active_get_disks()[array_disk_id - 1]
        return cls.get_real_disk_id(disk)


class _ScheduleModel(models.Model):
    """
    Abstract class with relation to PeriodicTask and lazy cron schedule and active properties.
    """
    PT = PeriodicTask
    _active = None  # cached enabled attribute
    _schedule = None  # cached crontab entry
    periodic_task = models.ForeignKey(PT, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        app_label = 'vms'
        abstract = True

    # noinspection PyMethodMayBeStatic
    def _new_periodic_task(self):
        """Return instance of PeriodicTask. Define in descendant class"""
        return NotImplemented  # return self.PT(name=, task=, args=, kwargs=, expires=)

    def _save_crontab(self, c):
        """Save crontab instance"""
        c.minute, c.hour, c.day_of_month, c.month_of_year, c.day_of_week = self.schedule.split()
        c.save()
        return c

    @staticmethod
    def crontab_to_schedule(c):
        """Return string representation of CrontabSchedule model"""
        def s(f):
            return f and str(f).replace(' ', '') or '*'

        return '%s %s %s %s %s' % (s(c.minute), s(c.hour), s(c.day_of_month), s(c.month_of_year), s(c.day_of_week))

    @property
    def active(self):
        """Return enabled boolean from periodic task"""
        if self._active is None:  # init
            if self.periodic_task:
                self._active = self.periodic_task.enabled
            else:
                self._active = True  # default
        return self._active

    @active.setter
    def active(self, value):
        """Cache active attribute - will be updated/created later in save()"""
        self._active = value

    @property
    def schedule(self):
        """Return cron entry from periodic task"""
        if self._schedule is None and self.periodic_task and self.periodic_task.crontab:  # init
            self._schedule = self.crontab_to_schedule(self.periodic_task.crontab)

        return self._schedule

    @schedule.setter
    def schedule(self, value):
        """Cache cron entry - will be updated/created later in save()"""
        self._schedule = value

    @transaction.atomic
    def save(self, *args, **kwargs):
        """Create or update periodic task and cron schedule in DB"""
        # Save first, because the periodic_task needs this object's ID
        super().save(*args, **kwargs)

        do_save = False
        pt = self.periodic_task

        if not pt:
            pt = self._new_periodic_task()

        if not pt.crontab:
            pt.crontab = self._save_crontab(CrontabSchedule())
            do_save = True
        elif self.schedule != self.crontab_to_schedule(pt.crontab):
            self._save_crontab(pt.crontab)
            do_save = True  # Need to update PeriodicTask, because it will signal the Scheduler to reload

        if self.active != pt.enabled:
            pt.enabled = self.active
            do_save = True

        if not pt.pk:
            pt.save()  # New periodic task object
            self.periodic_task = pt
            self.save(update_fields=('periodic_task',))  # Update this object
        elif do_save:
            pt.save(update_fields=('enabled', 'crontab', 'date_changed'))  # Update periodic task

    # noinspection PyUnusedLocal
    @staticmethod
    def post_delete_schedule(sender, instance, **kwargs):
        """Cascade delete - call from signal"""
        if instance.periodic_task:
            if instance.periodic_task.crontab:
                instance.periodic_task.crontab.delete()
            else:
                instance.periodic_task.delete()
