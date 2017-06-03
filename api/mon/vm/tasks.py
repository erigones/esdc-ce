from celery.utils.log import get_task_logger
from django.utils.six import text_type

from que.erigonesd import cq
from que.mgmt import MgmtTask
from que.exceptions import MgmtTaskException
from que.utils import dc_id_from_task_id
from api.task.utils import mgmt_task, mgmt_lock
from api.mon.log import save_task_log
from api.mon.zabbix import LOG, getZabbix, ZabbixError
from api.mon.messages import LOG_MON_VM_UPDATE, LOG_MON_VM_DELETE
from api.mon.vm.utils import VmMonInternalTask
from vms.signals import vm_deployed, vm_json_active_changed, vm_node_changed, vm_notcreated
from vms.models import Dc, Vm

__all__ = ('mon_vm_sla', 'mon_vm_history', 'mon_vm_sync', 'mon_vm_disable', 'mon_vm_delete')

logger = get_task_logger(__name__)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.vm.tasks.mon_vm_sla', base=MgmtTask)
@mgmt_task()
def mon_vm_sla(task_id, vm_hostname, yyyymm, vm_node_history, **kwargs):
    """
    Return SLA (%) for VM / month.
    """
    dc = Dc.objects.get_by_id(int(dc_id_from_task_id(task_id)))

    try:
        sla = getZabbix(dc).vm_sla(vm_node_history)
    except ZabbixError as exc:
        raise MgmtTaskException(text_type(exc))

    result = {
        'hostname': vm_hostname,
        'since': vm_node_history[0]['since'],
        'until': vm_node_history[-1]['till'],
        'sla': round(sla, 4),
    }

    return result


# noinspection PyUnusedLocal
@cq.task(name='api.mon.vm.tasks.mon_vm_history', base=MgmtTask)
@mgmt_task()
def mon_vm_history(task_id, vm_uuid, items, zhistory, result, items_search, **kwargs):
    """
    Return server history data for selected graph and period.
    """
    dc = Dc.objects.get_by_id(int(dc_id_from_task_id(task_id)))

    try:
        history = getZabbix(dc).vm_history(vm_uuid, items, zhistory, result['since'], result['until'],
                                           items_search=items_search)
    except ZabbixError as exc:
        raise MgmtTaskException(text_type(exc))

    result.update(history)

    return result


# noinspection PyUnusedLocal
@cq.task(name='api.mon.vm.tasks.mon_vm_sync', base=VmMonInternalTask)
@mgmt_lock(key_kwargs=('vm_uuid',), wait_for_release=True)
@save_task_log(LOG_MON_VM_UPDATE)
def mon_vm_sync(task_id, sender, vm_uuid=None, log=LOG, **kwargs):
    """
    Create or synchronize zabbix host according to VM.
    """
    assert vm_uuid
    vm = log.obj = Vm.objects.select_related('dc', 'slavevm').get(uuid=vm_uuid)
    log.dc_id = vm.dc.id

    if vm.is_slave_vm():
        logger.info('Ignoring VM %s zabbix sync, because it is a slave VM', vm)
        return None

    if vm.is_deploying():
        logger.warn('Ignoring VM %s zabbix sync, because it is currently being deployed', vm)
        return None

    # This can be also called via vm_zoneid_changed signal, where VM's DC is not available and
    # monitoring can be disabled in that DC
    if not vm.dc.settings.MON_ZABBIX_ENABLED:
        logger.info('Skipping VM %s zabbix sync, because zabbix module is completely disabled in DC %s', vm, vm.dc)
        return None

    zx = getZabbix(vm.dc)
    force_update = kwargs.get('force_update', False)

    return zx.vm_sync(vm, force_update=force_update, task_log=log)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.vm.tasks.mon_vm_disable', base=VmMonInternalTask)
@mgmt_lock(key_kwargs=('vm_uuid',), wait_for_release=True)
@save_task_log(LOG_MON_VM_UPDATE)
def mon_vm_disable(task_id, sender, vm_uuid=None, log=LOG, **kwargs):
    """
    Switch host status in zabbix to not monitored.
    """
    assert vm_uuid
    vm = log.obj = Vm.objects.select_related('dc').get(uuid=vm_uuid)

    if vm.is_zabbix_sync_active() or vm.is_external_zabbix_sync_active():
        return getZabbix(vm.dc).vm_disable(vm, task_log=log)
    else:
        logger.info('Zabbix synchronization completely disabled for VM %s', vm)
        return None


# noinspection PyUnusedLocal
@cq.task(name='api.mon.vm.tasks.mon_vm_delete', base=VmMonInternalTask)
@mgmt_lock(key_kwargs=('vm_uuid',), wait_for_release=True)
@save_task_log(LOG_MON_VM_DELETE)
def mon_vm_delete(task_id, sender, vm_uuid=None, vm_hostname=None, vm_alias=None, dc_id=None, zabbix_sync=None,
                  external_zabbix_sync=None, log=LOG, **kwargs):
    """
    Remove host from zabbix.
    """
    assert vm_uuid
    assert dc_id
    assert zabbix_sync is not None
    assert external_zabbix_sync is not None
    # Create dummy VM object - used just to get zabbix_id and log things
    vm = Vm(uuid=vm_uuid, hostname=vm_hostname, alias=vm_alias)
    log.obj = vm.log_list

    if zabbix_sync or external_zabbix_sync:
        dc = Dc.objects.get_by_id(dc_id)
        return getZabbix(dc).vm_delete(Vm(uuid=vm_uuid, hostname=vm_hostname), internal=zabbix_sync,
                                       external=external_zabbix_sync, task_log=log)
    else:
        logger.info('Zabbix synchronization completely disabled for VM %s', vm_uuid)
        return None


# erigonesd context signals:
vm_deployed.connect(mon_vm_sync.call)
vm_json_active_changed.connect(mon_vm_sync.call)
vm_node_changed.connect(mon_vm_sync.call)
vm_notcreated.connect(mon_vm_disable.call)
# gunicorn context signals are connected in api.signals:
# vm_updated -> mon_vm_sync
# vm_undefined -> mon_vm_delete
