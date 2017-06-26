from api.mon.backends.zabbix.monitor import Zabbix, get_zabbix, del_zabbix

get_monitoring = get_zabbix

del_monitoring = del_zabbix

MonitoringBackendClass = Zabbix

__all__ = ('get_monitoring', 'del_monitoring', 'MonitoringBackendClass')
