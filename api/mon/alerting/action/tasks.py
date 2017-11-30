from celery.utils.log import get_task_logger
from django.utils.six import text_type

from api.mon import get_monitoring, MonitoringError
from api.task.utils import mgmt_task
from que.erigonesd import cq
from que.exceptions import MgmtTaskException
from que.mgmt import MgmtTask
from vms.models import Dc

__all__ = ('mon_action_list', 'mon_action_create', 'mon_action_update', 'mon_action_delete', 'mon_action_get')

logger = get_task_logger(__name__)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.alerting.action.tasks.mon_action_list', base=MgmtTask)
@mgmt_task()
def mon_action_list(task_id, dc_id, **kwargs):

    dc = Dc.objects.get_by_id(int(dc_id))

    try:
        zabbix_actions = get_monitoring(dc).action_list()
    except MonitoringError as exc:
        raise MgmtTaskException(text_type(exc))

    return [
        {
            'name': t.name,
            'id': t.zabbix_id,
            # ... TODO fill
        }
        for t in zabbix_actions
    ]


@cq.task(name='api.mon.alerting.action.tasks.mon_action_create', base=MgmtTask)
@mgmt_task()
def mon_action_create(task_id, dc_id, action, **kwargs):
    dc = Dc.objects.get_by_id(int(dc_id))
    get_monitoring(dc).action_create(action)


@cq.task(name='api.mon.alerting.action.tasks.mon_action_update', base=MgmtTask)
@mgmt_task()
def mon_action_update(task_id, dc_id, action, **kwargs):
    dc = Dc.objects.get_by_id(int(dc_id))
    get_monitoring(dc).action_update(action)


@cq.task(name='api.mon.alerting.action.tasks.mon_action_get', base=MgmtTask)
@mgmt_task()
def mon_action_get():
    pass  # Fail loudly if Does not exist


@cq.task(name='api.mon.alerting.action.tasks.mon_action_delete', base=MgmtTask)
@mgmt_task()
def mon_action_delete(task_id, dc_id, action_name, **kwargs):
    dc = Dc.objects.get_by_id(int(dc_id))
    get_monitoring(dc).action_delete(action_name)  # Fail loudly if doesnt exist


# todo dont forget to update the task log after task is complete
