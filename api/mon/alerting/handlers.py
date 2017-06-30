from .tasks import mon_all_groups_sync


# noinspection PyUnusedLocal
def dc_settings_changed_handler(task_id, dc, old_settings, new_settings):
    alerting_related_settings = (
        'MON_ZABBIX_MONITORING_ENABLED',
        'MON_ZABBIX_SERVER',
        'MON_ZABBIX_SERVER_SSL_VERIFY',
        'MON_ZABBIX_HTTP_USERNAME',
        'MON_ZABBIX_HTTP_PASSWORD',

    )
    if any(old_settings.get(setting) != new_settings.get(setting) for setting in alerting_related_settings):
        mon_all_groups_sync.call(sender='dc_settings_changed_handler', dc_name=dc.name)
