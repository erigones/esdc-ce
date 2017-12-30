from celery.utils.log import get_task_logger

from api.mon import get_monitoring, del_monitoring
from api.mon.exceptions import RemoteObjectDoesNotExist, RemoteObjectAlreadyExists
from api.mon.vm.tasks import mon_vm_sync
from api.mon.node.tasks import mon_node_sync
# noinspection PyProtectedMember
from api.mon.alerting.tasks import mon_all_groups_sync
from api.task.utils import mgmt_lock, mgmt_task
from que.exceptions import MgmtTaskException
from que.erigonesd import cq
from que.internal import InternalTask
from que.mgmt import MgmtTask
from vms.models import Dc, Node

__all__ = (
    'mon_sync_all',
    'mon_template_list',
    'mon_hostgroup_list',
    'mon_hostgroup_get',
    'mon_hostgroup_create',
    'mon_hostgroup_delete',
)

logger = get_task_logger(__name__)


def mon_clear_zabbix_cache(dc, full=True):
    """
    Clear Zabbix instance from global zabbix cache used by get_monitoring() if full==True.
    Reset internal zabbix instance cache if full==False and the zabbix instance exists in global zabbix cache.
    Should be reviewed with every new backend implemented.
    """
    if full:
        if del_monitoring(dc):
            logger.info('Zabbix instance for DC "%s" was successfully removed from global cache', dc)
        else:
            logger.info('Zabbix instance for DC "%s" was not found in global cache', dc)
    else:
        zx = get_monitoring(dc)
        zx.reset_cache()
        logger.info('Cleared cache for zabbix instance %s in DC "%s"', zx, dc)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_sync_all', base=InternalTask)
@mgmt_lock(key_args=(1,), wait_for_release=True)
def mon_sync_all(task_id, dc_id, clear_cache=True, sync_groups=True, sync_nodes=True, sync_vms=True, **kwargs):
    """
    Clear Zabbix cache and sync everything in Zabbix.
    Related to a specific DC.
    Triggered by dc_settings_changed signal.
    """
    dc = Dc.objects.get_by_id(int(dc_id))

    if clear_cache:
        logger.info('Clearing zabbix cache in DC %s', dc)
        mon_clear_zabbix_cache(dc)
        get_monitoring(dc)  # Cache new Zabbix instance for tasks below

    if sync_groups:
        logger.info('Running monitoring group synchronization for all user groups in DC %s', dc)
        mon_all_groups_sync.call(task_id, dc_name=dc.name)

    if sync_nodes:
        logger.info('Running monitoring host synchronization for all compute nodes')
        for node in Node.all():
            mon_node_sync.call(task_id, node_uuid=node.uuid)

    if sync_vms:
        logger.info('Running monitoring host synchronization for all VMs in DC %s', dc)
        for vm_uuid in dc.vm_set.values_list('uuid', flat=True):
            mon_vm_sync.call(task_id, vm_uuid=vm_uuid)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_template_list', base=MgmtTask)
@mgmt_task(log_exception=False)
def mon_template_list(task_id, dc_id, full=False, extended=False, **kwargs):
    """
    Return list of templates available in Zabbix.
    """
    dc = Dc.objects.get_by_id(int(dc_id))

    return get_monitoring(dc).template_list(full=full, extended=extended)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_hostgroup_list', base=MgmtTask)
@mgmt_task(log_exception=False)
def mon_hostgroup_list(task_id, dc_id, dc_bound=True, full=False, extended=False, **kwargs):
    """
    Return list of hostgroups available in Zabbix.
    """
    dc = Dc.objects.get_by_id(int(dc_id))

    return get_monitoring(dc).hostgroup_list(dc_bound=dc_bound, full=full, extended=extended)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_hostgroup_get', base=MgmtTask)
@mgmt_task(log_exception=False)
def mon_hostgroup_get(task_id, dc_id, hostgroup_name, dc_bound=True, **kwargs):
    dc = Dc.objects.get_by_id(int(dc_id))
    mon = get_monitoring(dc)

    try:
        return mon.hostgroup_detail(hostgroup_name, dc_bound=dc_bound)
    except RemoteObjectDoesNotExist as exc:
        raise MgmtTaskException(exc.detail)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_hostgroup_create', base=MgmtTask)
@mgmt_task(log_exception=True)
def mon_hostgroup_create(task_id, dc_id, hostgroup_name, dc_bound=True, **kwargs):
    dc = Dc.objects.get_by_id(int(dc_id))
    mon = get_monitoring(dc)

    try:
        result = mon.hostgroup_create(hostgroup_name, dc_bound=dc_bound)
    except RemoteObjectAlreadyExists as exc:
        raise MgmtTaskException(exc.detail)

    detail = 'Monitoring hostgroup "%s" was successfully created' % hostgroup_name
    mon.task_log_success(task_id, obj=mon.server_class(dc), detail=detail, **kwargs['meta'])

    return result


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_hostgroup_delete', base=MgmtTask)
@mgmt_task(log_exception=True)
def mon_hostgroup_delete(task_id, dc_id, hostgroup_name, dc_bound=True, **kwargs):
    dc = Dc.objects.get_by_id(int(dc_id))
    mon = get_monitoring(dc)

    try:
        result = mon.hostgroup_delete(hostgroup_name, dc_bound=dc_bound)  # Fail loudly if doesnt exist
    except RemoteObjectDoesNotExist as exc:
        raise MgmtTaskException(exc.detail)

    detail = 'Monitoring hostgroup "%s" was successfully deleted' % hostgroup_name
    mon.task_log_success(task_id, obj=mon.server_class(dc), detail=detail, **kwargs['meta'])

    return result
