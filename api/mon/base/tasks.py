from celery.utils.log import get_task_logger
from django.utils.six import text_type

from api.mon.zabbix import getZabbix, delZabbix, ZabbixError
from api.task.utils import mgmt_lock, mgmt_task
from que.erigonesd import cq
from que.exceptions import MgmtTaskException
from que.internal import InternalTask
from que.mgmt import MgmtTask
from vms.models import Dc, DefaultDc

__all__ = ('mon_clear_zabbix_cache',)

logger = get_task_logger(__name__)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_clear_zabbix_cache', base=InternalTask)
@mgmt_lock(key_args=(1,), wait_for_release=True)
def mon_clear_zabbix_cache(task_id, dc_id, full=True):
    """
    Clear Zabbix instance from global zabbix cache used by getZabbix() if full==True.
    Reset internal zabbix instance cache if full==False and the zabbix instance exists in global zabbix cache.
    """
    dc = Dc.objects.get_by_id(int(dc_id))

    if full:
        if delZabbix(dc):
            logger.info('Zabbix instance for DC "%s" was successfully removed from global cache', dc)
        else:
            logger.info('Zabbix instance for DC "%s" was not found in global cache', dc)
    else:
        zx = getZabbix(dc)
        zx.reset_cache()
        logger.info('Cleared cache for zabbix instance %s in DC "%s"', zx, dc)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.node.tasks.mon_template_list', base=MgmtTask)
@mgmt_task()
def mon_template_list(task_id, dc_id, **kwargs):
    """
    Return list of templates available in Zabbix.
    """
    dc = Dc.objects.get_by_id(int(dc_id))

    try:
        zabbix_templates = getZabbix(dc).template_list()
    except ZabbixError as exc:
        raise MgmtTaskException(text_type(exc))

    return {'templates': [{'name': templ['host'],
             'visible_name': templ['name'],
             'desc': templ['description'],
             'id': templ['templateid']} for templ in zabbix_templates]
           }
