from __future__ import absolute_import

from celery import Task

from que import Q_MGMT
from que.erigonesd import cq
from que.utils import generate_internal_task_id

ERIGONES_TASK_USER = cq.conf.ERIGONES_TASK_USER


# noinspection PyAbstractClass
class InternalTask(Task):
    """
    Abstract task for internal tasks that nobody should know about, running in mgmt queue.
    """
    abstract = True

    def call(self, *args, **kwargs):
        """
        Creates task in mgmt queue with same arguments. Returns task_id.
        """
        task_id = generate_internal_task_id()
        # First argument is always task TD
        args = list(args)
        args.insert(0, task_id)

        # Run task
        return self.apply_async(args=args, kwargs=kwargs, queue=Q_MGMT, task_id=task_id,
                                expires=None, add_to_parent=False)
