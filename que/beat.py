from __future__ import absolute_import

from celery.beat import PersistentScheduler
from django_celery_beat.schedulers import DatabaseScheduler

from que.utils import task_id_from_string


class ESDCScheduler(PersistentScheduler):
    """
    Custom beat scheduler, because we need to modify the task id manually.
    """
    def apply_async(self, entry, *args, **kwargs):
        entry.options['task_id'] = task_id_from_string(self.app.conf.ERIGONES_TASK_USER)
        return super(ESDCScheduler, self).apply_async(entry, *args, **kwargs)


class ESDCDatabaseScheduler(DatabaseScheduler):
    """
    Custom beat database scheduler, because we need to modify the task id manually.
    """
    def reserve(self, entry):
        new_entry = super(ESDCDatabaseScheduler, self).reserve(entry)
        new_entry.options['task_id'] = task_id_from_string(self.app.conf.ERIGONES_TASK_USER)
        return new_entry
