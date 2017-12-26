from celery.utils.log import get_task_logger

from api.mon import get_monitoring
from api.mon.messages import LOG_MON_HOSTGROUP_CREATE
from api.mon.exceptions import RemoteObjectDoesNotExist, RemoteObjectAlreadyExists
from api.task.utils import mgmt_task
from que.erigonesd import cq
from que.exceptions import MgmtTaskException
from que.mgmt import MgmtTask
from vms.models import Dc

__all__ = ('mon_action_list', 'mon_action_get', 'mon_action_create', 'mon_action_update', 'mon_action_delete')

logger = get_task_logger(__name__)

ACTION_NOT_FOUND = 'Monitoring action "%s" not found'
ACTION_ALREADY_EXISTS = 'Monitoring action "%s" already exists'


def _log_hostgroup_created(mon, task_id, name):
    detail = 'Monitoring hostgroup "%s" was successfully created' % name
    mon.task_log_success(task_id, msg=LOG_MON_HOSTGROUP_CREATE, detail=detail)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.alerting.action.tasks.mon_action_list', base=MgmtTask)
@mgmt_task(log_exception=False)
def mon_action_list(task_id, dc_id, full=False, extended=False, **kwargs):
    dc = Dc.objects.get_by_id(int(dc_id))
    mon = get_monitoring(dc)

    return mon.action_list(full=full, extended=extended)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.alerting.action.tasks.mon_action_get', base=MgmtTask)
@mgmt_task(log_exception=False)
def mon_action_get(task_id, dc_id, action_name, **kwargs):
    dc = Dc.objects.get_by_id(int(dc_id))
    mon = get_monitoring(dc)

    try:
        return mon.action_detail(action_name)
    except RemoteObjectDoesNotExist:
        raise MgmtTaskException(ACTION_NOT_FOUND % action_name)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.alerting.action.tasks.mon_action_create', base=MgmtTask)
@mgmt_task(log_exception=True)
def mon_action_create(task_id, dc_id, action_name, action_data=None, **kwargs):
    assert action_data is not None

    dc = Dc.objects.get_by_id(int(dc_id))
    mon = get_monitoring(dc)

    try:
        result = mon.action_create(action_name, action_data)
    except RemoteObjectAlreadyExists:
        raise MgmtTaskException(ACTION_ALREADY_EXISTS % action_name)

    detail = 'Monitoring action "%s" was successfully created' % action_name
    mon.task_log_success(task_id, detail=detail, **kwargs['meta'])

    for hostgroup_name in result.get('hostgroups_created', []):
        _log_hostgroup_created(mon, task_id, hostgroup_name)

    return result


# noinspection PyUnusedLocal
@cq.task(name='api.mon.alerting.action.tasks.mon_action_update', base=MgmtTask)
@mgmt_task(log_exception=True)
def mon_action_update(task_id, dc_id, action_name, action_data=None, **kwargs):
    assert action_data is not None

    dc = Dc.objects.get_by_id(int(dc_id))
    mon = get_monitoring(dc)

    try:
        result = mon.action_update(action_name, action_data)
    except RemoteObjectDoesNotExist:
        raise MgmtTaskException(ACTION_NOT_FOUND % action_name)

    detail = 'Monitoring action "%s" was successfully updated' % action_name
    mon.task_log_success(task_id, detail=detail, **kwargs['meta'])

    for hostgroup_name in result.get('hostgroups_created', []):
        _log_hostgroup_created(mon, task_id, hostgroup_name)

    return result


# noinspection PyUnusedLocal
@cq.task(name='api.mon.alerting.action.tasks.mon_action_delete', base=MgmtTask)
@mgmt_task(log_exception=True)
def mon_action_delete(task_id, dc_id, action_name, action_data=None, **kwargs):
    dc = Dc.objects.get_by_id(int(dc_id))
    mon = get_monitoring(dc)

    try:
        result = mon.action_delete(action_name)  # Fail loudly if doesnt exist
    except RemoteObjectDoesNotExist:
        raise MgmtTaskException(ACTION_NOT_FOUND % action_name)

    detail = 'Monitoring action "%s" was successfully deleted' % action_name
    mon.task_log_success(task_id, detail=detail, **kwargs['meta'])

    return result