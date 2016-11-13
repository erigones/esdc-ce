from logging import CRITICAL, getLevelName
from functools import wraps
from django.utils.decorators import available_attrs
from celery import states
from celery.utils.log import get_task_logger

from api.decorators import catch_exception
from api.task.utils import task_log

logger = get_task_logger(__name__)


class DetailLog(list):
    """
    List-like object for collecting log lines for task log detail.
    """
    def __init__(self, task_id, msg, obj=None):
        super(DetailLog, self).__init__()
        self.task_id = task_id
        self.msg = msg
        self.obj = obj
        self.dc_id = None  # Do not change this, unless you know what you are doing (the "vm_zoneid_changed" case)

    def add(self, level, message):
        return self.append((level, message))

    def get_detail(self):
        return '\n'.join('%s: %s' % (getLevelName(level), message) for level, message in self)

    @catch_exception
    def save(self, status):
        """Save task log entry if result is not None"""
        if hasattr(status, '__iter__'):
            status = [i for i in status if i is not None]  # remove None from result

            if status:
                success = all(status)
            else:
                success = None
        else:
            success = status

        if success is None:
            return

        if success:
            task_status = states.SUCCESS
        else:
            task_status = states.FAILURE

        task_log(self.task_id, self.msg, obj=self.obj, task_status=task_status, task_result=True,
                 detail=self.get_detail(), dc_id=self.dc_id, update_user_tasks=False)


def save_task_log(msg):
    """
    Decorator used by monitoring tasks. It creates a unique list-like object for collecting monitoring logs and is
    responsible for creating a task log entry after the monitoring task is finished.
    """
    def wrap(fun):
        @wraps(fun, assigned=available_attrs(fun))
        def inner(task_id, sender, **kwargs):
            logger.info('Primary task %s issued a secondary mgmt monitoring task %s', sender, task_id)
            status = None
            # Every monitoring task should collect logs
            # NOTE: However, the monitoring task is responsible for setting up the object related to the log entry
            kwargs['log'] = log = DetailLog(sender, msg)

            try:
                status = fun(task_id, sender, **kwargs)
            except Exception as exc:
                status = False
                log.add(CRITICAL, exc)
                raise exc
            finally:
                log.save(status)

            return status
        return inner
    return wrap
