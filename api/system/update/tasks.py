from celery.utils.log import get_task_logger
from django.conf import settings

from api.task.utils import mgmt_task, task_log_success
from api.system.update.utils import process_update_reply
from api.system.update.events import SystemUpdateStarted, SystemUpdateFinished
from que.erigonesd import cq
from que.exceptions import MgmtTaskException
from que.mgmt import MgmtTask
from que.handlers import update_command
from vms.models import Dc

__all__ = ('system_update',)

logger = get_task_logger(__name__)


# noinspection PyUnusedLocal
@cq.task(name='api.system.update.tasks.system_update', base=MgmtTask)
@mgmt_task(log_exception=True)
def system_update(task_id, dc_id=None, version=None, key=None, cert=None, force=None, **kwargs):
    """
    Updated system on mgmt by running esdc-git-update.
    """
    assert dc_id
    assert version

    SystemUpdateStarted(task_id).send()  # Send info to all active socket.io users
    error = None

    try:
        dc = Dc.objects.get_by_id(dc_id)
        assert dc.is_default()

        reply = update_command(version, key=key, cert=cert, force=force, sudo=not settings.DEBUG, run=True)
        result, error = process_update_reply(reply, 'system', version, logger=logger)

        if error:
            raise MgmtTaskException(result['message'])
        else:
            task_log_success(task_id, kwargs['meta'].get('msg'), obj=dc, task_result=result)

        return result
    finally:
        SystemUpdateFinished(task_id, error=error).send()  # Send info to all active socket.io users
