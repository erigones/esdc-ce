from api.mon.backends.abstract.server import AbstractMonitoringServer


class ZabbixMonitoringServer(AbstractMonitoringServer):
    """
    Dummy model for representing a Zabbix monitoring server in a DC.
    """
    Meta = AbstractMonitoringServer.Meta

    def __init__(self, dc):
        dc_settings = dc.settings
        assert dc_settings.MON_ZABBIX_ENABLED
        self.uri = dc_settings.MON_ZABBIX_SERVER
        self.name = self.uri.split('/')[2]  # https://<server>
        self.address = self.name
        self.connection_id = hash((dc_settings.MON_ZABBIX_USERNAME, dc_settings.MON_ZABBIX_PASSWORD, self.uri))
        super(ZabbixMonitoringServer, self).__init__(dc)
