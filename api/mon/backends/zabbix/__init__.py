from api.mon.backends.zabbix.monitor import Zabbix, get_zabbix, del_zabbix
from api.mon.backends.zabbix.server import ZabbixMonitoringServer

get_monitoring = get_zabbix

del_monitoring = del_zabbix

MonitoringBackendClass = Zabbix

MonitoringServerClass = ZabbixMonitoringServer

__all__ = ('get_monitoring', 'del_monitoring', 'MonitoringBackendClass', 'MonitoringServerClass')
