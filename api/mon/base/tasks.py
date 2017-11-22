from celery.utils.log import get_task_logger
from django.utils.six import text_type

from que.utils import is_task_dc_bound

from api.mon import get_monitoring, del_monitoring, MonitoringError
from api.task.utils import mgmt_lock, mgmt_task
from que.erigonesd import cq
from que.exceptions import MgmtTaskException
from que.internal import InternalTask
from que.mgmt import MgmtTask
from vms.models import Dc, Vm

__all__ = ('mon_clear_zabbix_cache', 'mon_template_list', 'mon_hostgroup_list', 'mon_alert_list')

logger = get_task_logger(__name__)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_clear_zabbix_cache', base=InternalTask)
@mgmt_lock(key_args=(1,), wait_for_release=True)
def mon_clear_zabbix_cache(task_id, dc_id, full=True):
    """
    Clear Zabbix instance from global zabbix cache used by get_monitoring() if full==True.
    Reset internal zabbix instance cache if full==False and the zabbix instance exists in global zabbix cache.
    Should be reviewed with every new backend implemented.
    """
    dc = Dc.objects.get_by_id(int(dc_id))

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
@cq.task(name='api.mon.base.tasks.mon_template_list', base=MgmtTask)
@mgmt_task()
def mon_template_list(task_id, dc_id, **kwargs):
    """
    Return list of templates available in Zabbix.
    """
    dc = Dc.objects.get_by_id(int(dc_id))

    try:
        zabbix_templates = get_monitoring(dc).template_list()
    except MonitoringError as exc:
        raise MgmtTaskException(text_type(exc))

    return [
        {
            'name': t['host'],
            'visible_name': t['name'],
            'desc': t['description'],
            'id': t['templateid'],
        }
        for t in zabbix_templates
    ]


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_hostgroup_list', base=MgmtTask)
@mgmt_task()
def mon_hostgroup_list(task_id, dc_id, **kwargs):
    """
    Return list of hostgroups available in Zabbix.
    """
    dc = Dc.objects.get_by_id(int(dc_id))
    if is_task_dc_bound(task_id):
        prefix = dc.name
    else:
        prefix = ''

    try:
        zabbix_hostgroups = get_monitoring(dc).hostgroup_list(prefix=prefix)
    except MonitoringError as exc:
        raise MgmtTaskException(text_type(exc))

    return [
        {
            'name': t['name'],
            'id': t['groupid'],
        }
        for t in zabbix_hostgroups
    ]


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_alert_list', base=MgmtTask)
@mgmt_task()
def mon_alert_list(task_id, dc_id, *args, **kwargs):
    """
    Return list of alerts available in Zabbix.
    """
    dc = Dc.objects.get_by_id(int(dc_id))

    if is_task_dc_bound(task_id):
        kwargs['prefix'] = dc.name

        # set hosts_or_groups to hosts in this DC.
        vms = Vm.objects.filter(dc=dc)
        kwargs['hosts_or_groups'] = [vm.hostname for vm in vms]
    else:
        kwargs['prefix'] = ''

    try:
        zabbix_alerts = get_monitoring(dc).alert_list(*args, **kwargs)
    except MonitoringError as exc:
        raise MgmtTaskException(text_type(exc))
    return [
        {
            'eventid': t['eventid'],
            'prio': t['prio'],
            'hostname': t['hostname'],
            'desc': t['desc'],
            'age': t['age'],
            'ack': t['ack'],
            'comments': t['comments'],
            'latest_data': t['latest_data'],
            'last_change': t['last_change'],
            'events': t['events'],
        }
        for t in zabbix_alerts
    ]
