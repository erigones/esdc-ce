from api.mon.backends.zabbix.containers.base import ZabbixBaseContainer


class ZabbixTemplateContainer(ZabbixBaseContainer):
    """
    Container class for the Zabbix Template object.
    """
    ZABBIX_ID_ATTR = 'templateid'

    @classmethod
    def from_zabbix_data(cls, zapi, zabbix_object):
        return cls(zabbix_object['host'], zapi=zapi, zabbix_object=zabbix_object)

    @classmethod
    def all(cls, zapi):
        params = {'output': ['name', 'host', 'templateid', 'description']}
        response = cls.call_zapi(zapi, 'template.get', params=params)

        return [cls.from_zabbix_data(zapi, item) for item in response]

    @property
    def as_mgmt_data(self):
        zabbix_object = self.zabbix_object

        return {
            'name': zabbix_object['host'],
            'visible_name': zabbix_object['name'],
            'desc': zabbix_object['description'],
            'id': int(zabbix_object['templateid']),
        }
