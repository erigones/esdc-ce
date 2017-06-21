from api.mon.backends.zabbix.monitor import Zabbix, getZabbix, delZabbix

get_monitoring = getZabbix

del_monitoring = delZabbix

MonitoringBackendClass = Zabbix

__all__ = ('get_monitoring', 'del_monitoring', 'MonitoringBackendClass')
