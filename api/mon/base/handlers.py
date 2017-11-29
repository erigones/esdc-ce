from logging import getLogger

from api.decorators import catch_exception
from api.mon.base.tasks import mon_sync_all

logger = getLogger(__name__)


MON_SERVER_RELATED_SETTINGS = (
    'MON_ZABBIX_MONITORING_ENABLED',
    'MON_ZABBIX_SERVER',
    'MON_ZABBIX_SERVER_SSL_VERIFY',
    'MON_ZABBIX_USERNAME',
    'MON_ZABBIX_PASSWORD',
    'MON_ZABBIX_HTTP_USERNAME',
    'MON_ZABBIX_HTTP_PASSWORD',
)

MON_NODE_RELATED_SETTINGS = (
    'MON_ZABBIX_NODE_SYNC',
    'MON_ZABBIX_HOSTGROUP_NODE',
    'MON_ZABBIX_HOSTGROUPS_NODE',
    'MON_ZABBIX_TEMPLATES_NODE',
)

MON_VM_RELATED_SETTINGS = (
    'MON_ZABBIX_VM_SYNC',
    'MON_ZABBIX_HOSTGROUP_VM',
    'MON_ZABBIX_HOSTGROUPS_VM',
    'MON_ZABBIX_TEMPLATES_VM',
    'MON_ZABBIX_TEMPLATES_VM_MAP_TO_TAGS',
    'MON_ZABBIX_TEMPLATES_VM_NIC',
    'MON_ZABBIX_TEMPLATES_VM_DISK',
    'MON_ZABBIX_HOST_VM_PROXY',
)


# noinspection PyUnusedLocal
@catch_exception
def mon_settings_changed_handler(task_id, dc, old_settings, new_settings):
    """
    Handle changes in MON_* DC settings; triggered by dc_settings_changed signal.
    """
    changed_mon_settings = {opt for opt in old_settings if (opt.startswith('MON_ZABBIX') and
                                                            old_settings.get(opt) != new_settings.get(opt))}

    if changed_mon_settings:
        logger.info('Monitoring settings have changed in DC %s', dc)
        server_related_settings_changed = bool(changed_mon_settings.intersection(MON_SERVER_RELATED_SETTINGS))
        vm_related_settings_changed = bool(changed_mon_settings.intersection(MON_VM_RELATED_SETTINGS))
        node_related_settings_changed = bool(changed_mon_settings.intersection(MON_NODE_RELATED_SETTINGS))
        mon_sync_all.call(
            dc.id,
            sync_groups=server_related_settings_changed,
            sync_nodes=dc.is_default() and (server_related_settings_changed or node_related_settings_changed),
            sync_vms=server_related_settings_changed or vm_related_settings_changed
        )
