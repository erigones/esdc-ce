from celery.utils.log import get_task_logger
from django.utils.six import text_type

from api.mon import get_monitoring, MonitoringError
from api.task.utils import mgmt_task
from que.erigonesd import cq
from que.exceptions import MgmtTaskException
from que.mgmt import MgmtTask
from vms.models import Dc

__all__ = ('mon_action_list', )

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
