from celery.utils.log import get_task_logger

from api.mon import get_monitoring
from api.mon.constants import MON_OBJ_CREATED, MON_OBJ_UPDATED, MON_OBJ_DELETED
from api.mon.messages import MON_OBJ_HOSTGROUP, LOG_MON_HOSTGROUP_CREATE, MON_OBJ_ACTION, get_mon_action_detail
from api.task.utils import mgmt_task
from que.erigonesd import cq
from que.mgmt import MgmtTask
from vms.models import Dc

__all__ = ('mon_action_list', 'mon_action_get', 'mon_action_create', 'mon_action_update', 'mon_action_delete')

logger = get_task_logger(__name__)

ACTION_NOT_FOUND = MON_OBJ_ACTION + ' "{}" not found'
ACTION_ALREADY_EXISTS = MON_OBJ_ACTION + ' "{}" already exists'


def _log_hostgroup_created(mon, task_id, name):
    detail = get_mon_action_detail(MON_OBJ_HOSTGROUP, MON_OBJ_CREATED, name)
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

    return mon.action_detail(action_name)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.alerting.action.tasks.mon_action_create', base=MgmtTask)
@mgmt_task(log_exception=True)
def mon_action_create(task_id, dc_id, action_name, action_data=None, **kwargs):
    assert action_data is not None

    dc = Dc.objects.get_by_id(int(dc_id))
    mon = get_monitoring(dc)
    result = mon.action_create(action_name, action_data)
    detail = get_mon_action_detail(MON_OBJ_ACTION, MON_OBJ_CREATED, action_name)
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
    result = mon.action_update(action_name, action_data)
    detail = get_mon_action_detail(MON_OBJ_ACTION, MON_OBJ_UPDATED, action_name)
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
    result = mon.action_delete(action_name)  # Fail loudly if doesnt exist
    detail = get_mon_action_detail(MON_OBJ_ACTION, MON_OBJ_DELETED, action_name)
    mon.task_log_success(task_id, detail=detail, **kwargs['meta'])

    return result
