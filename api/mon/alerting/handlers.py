from api.mon.alerting.tasks import mon_all_groups_sync

ALERTING_RELATED_SETTINGS = (
    'MON_ZABBIX_MONITORING_ENABLED',
    'MON_ZABBIX_SERVER',
    'MON_ZABBIX_SERVER_SSL_VERIFY',
    'MON_ZABBIX_USERNAME',
    'MON_ZABBIX_PASSWORD',
    'MON_ZABBIX_HTTP_USERNAME',
    'MON_ZABBIX_HTTP_PASSWORD',
)


# noinspection PyUnusedLocal
def dc_settings_changed_handler(task_id, dc, old_settings, new_settings):
    if any(old_settings.get(setting) != new_settings.get(setting) for setting in ALERTING_RELATED_SETTINGS):
        mon_all_groups_sync.call(sender='dc_settings_changed_handler', dc_name=dc.name)
