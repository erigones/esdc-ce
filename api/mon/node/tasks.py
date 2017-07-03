from celery.utils.log import get_task_logger
from django.utils.six import text_type

from que.erigonesd import cq
from que.mgmt import MgmtTask
from que.exceptions import MgmtTaskException
from api.task.utils import mgmt_task, mgmt_lock
from api.mon.log import save_task_log
from api.mon import LOG, get_monitoring, MonitoringError
from api.mon.messages import LOG_MON_NODE_UPDATE, LOG_MON_NODE_DELETE
from api.mon.node.utils import NodeMonInternalTask
from vms.models import DefaultDc, Node
from vms.signals import node_created, node_json_changed

__all__ = ('mon_node_sla', 'mon_node_sync', 'mon_node_status_sync', 'mon_node_delete')

logger = get_task_logger(__name__)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.node.tasks.mon_node_sla', base=MgmtTask)
@mgmt_task()
def mon_node_sla(task_id, node_hostname, yyyymm, since, until, **kwargs):
    """
    Return SLA (%) for compute node / month.
    """
    try:
        sla = get_monitoring(DefaultDc()).node_sla(node_hostname, since, until)
    except MonitoringError as exc:
        raise MgmtTaskException(text_type(exc))

    return {
        'hostname': node_hostname,
        'since': since,
        'until': until,
        'sla': round(sla, 4),
    }


# noinspection PyUnusedLocal
@cq.task(name='api.mon.node.tasks.mon_node_history', base=MgmtTask)
@mgmt_task()
def mon_node_history(task_id, node_uuid, items, zhistory, result, items_search, **kwargs):
    """
    Return node's historical data for selected graph and period.
    """
    try:
        history = get_monitoring(DefaultDc()).node_history(node_uuid, items, zhistory, result['since'], result['until'],
                                                           items_search=items_search)
    except MonitoringError as exc:
        raise MgmtTaskException(text_type(exc))

    result.update(history)

    return result


# noinspection PyUnusedLocal
@cq.task(name='api.mon.node.tasks.mon_node_sync', base=NodeMonInternalTask)
@mgmt_lock(key_kwargs=('node_uuid',), wait_for_release=True)
@save_task_log(LOG_MON_NODE_UPDATE)
def mon_node_sync(task_id, sender, node_uuid=None, log=LOG, **kwargs):
    """
    Create or synchronize zabbix node host according to compute node.
    """
    assert node_uuid
    node = log.obj = Node.objects.get(uuid=node_uuid)

    return get_monitoring(DefaultDc()).node_sync(node, task_log=log)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.node.tasks.mon_node_status_sync', base=NodeMonInternalTask)
@mgmt_lock(key_kwargs=('node_uuid',), wait_for_release=True)
@save_task_log(LOG_MON_NODE_UPDATE)
def mon_node_status_sync(task_id, sender, node_uuid=None, log=LOG, **kwargs):
    """
    Switch host status in zabbix according to node status.
    """
    assert node_uuid
    node = log.obj = Node.objects.get(uuid=node_uuid)

    return get_monitoring(DefaultDc()).node_status_sync(node, task_log=log)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.node.tasks.mon_node_delete', base=NodeMonInternalTask)
@mgmt_lock(key_kwargs=('node_uuid',), wait_for_release=True)
@save_task_log(LOG_MON_NODE_DELETE)
def mon_node_delete(task_id, sender, node_uuid=None, node_hostname=None, log=LOG, **kwargs):
    """
    Remove host from zabbix.
    """
    assert node_uuid
    # Create dummy node object - used just to get zabbix_id and log things
    node = Node(uuid=node_uuid, hostname=node_hostname)
    log.obj = node.log_list

    return get_monitoring(DefaultDc()).node_delete(node, task_log=log)


# erigonesd context signals:
node_created.connect(mon_node_sync.call)
node_json_changed.connect(mon_node_sync.call)  # also used in api.node.define.node_define
# gunicorn context signals are connected in api.signals:
# mon_node_status_sync
# mon_node_delete
