import os
from django.conf import settings

from api.task.utils import mgmt_lock
from api.task.internal import InternalTask
from que.tasks import cq, get_task_logger
from api.mon.alerting.tasks import mon_all_groups_sync

__all__ = ('mgmt_worker_startup',)

logger = get_task_logger(__name__)

VM_ZABBIX_SYNC_REQUIRED_FILE = os.path.join(settings.RUNDIR, 'vm_zabbix_sync_required')


def vm_zabbix_sync(sender):
    """Sync all VMs with internal zabbix"""
    from api.mon.utils import get_mon_vms
    from api.mon.vm.tasks import mon_vm_sync

    for vm in get_mon_vms():
        logger.debug('Creating zabbix sync task for VM %s', vm)
        mon_vm_sync.call(sender, vm=vm)

    mon_all_groups_sync.call(sender=sender)


# noinspection PyUnusedLocal
@cq.task(name='api.system.tasks.mgmt_worker_startup', base=InternalTask)
@mgmt_lock(timeout=60, wait_for_release=True)
def mgmt_worker_startup(task_id, **kwargs):
    """Called by que.handlers.mgmt_worker_start during erigonesd startup"""
    if settings.DEBUG:
        logger.warning('DEBUG mode on => skipping mgmt worker startup task')
        return

    if settings.MON_ZABBIX_ENABLED and os.path.exists(VM_ZABBIX_SYNC_REQUIRED_FILE):
        logger.warning('Found %s => running zabbix sync for all VMs', VM_ZABBIX_SYNC_REQUIRED_FILE)
        vm_zabbix_sync(task_id)
        logger.info('Removed %s', VM_ZABBIX_SYNC_REQUIRED_FILE)
        os.remove(VM_ZABBIX_SYNC_REQUIRED_FILE)
