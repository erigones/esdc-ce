import re

from api.mon.backends.abstract import AbstractMonitoringBackend
from api.mon.backends.zabbix.utils import parse_zabbix_result
from api.mon.backends.zabbix.exceptions import ZabbixAPIError, RemoteObjectAlreadyExists


class ZabbixBaseContainer(object):
    """
    Base class for ZabbixUserContainer etc.
    As ZabbixUserGroupContainer.users contains instances of ZabbixUserContainer instances, making it a set allows us
     to do useful operations with it. Therefore, we implemented this class so that those instances can be part of a set.
    """
    NOTHING = AbstractMonitoringBackend.NOTHING
    CREATED = AbstractMonitoringBackend.CREATED
    UPDATED = AbstractMonitoringBackend.UPDATED
    DELETED = AbstractMonitoringBackend.DELETED

    RE_NAME_WITH_DC_PREFIX = re.compile(r'^:(?P<dc_name>.*):(?P<name>.+):$')
    TEMPLATE_NAME_WITH_DC_PREFIX = ':{dc_name}:{name}:'
    ZABBIX_ID_ATTR = NotImplemented

    zabbix_id = None
    zabbix_object = None

    def __init__(self, name, zapi=None, zabbix_object=None, **kwargs):
        self._name = name
        self._zapi = zapi
        self._api_response = None

        if zabbix_object:
            self.init(zabbix_object, **kwargs)

    def __repr__(self):
        return '{}(name={}) with zabbix_id {}'.format(self.__class__.__name__, self.name, self.zabbix_id)

    def __eq__(self, other):
        if hasattr(other, 'name') and issubclass(self.__class__, other.__class__):
            return self.name == other.name
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.name.__hash__()

    def init(self, zabbix_object, **kwargs):
        self.zabbix_object = zabbix_object
        self.zabbix_id = int(zabbix_object[self.ZABBIX_ID_ATTR])

    def reset(self):
        self.zabbix_object = None
        self.zabbix_id = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        raise ValueError('Name is immutable')

    @classmethod
    def call_zapi(cls, zapi, zapi_method, params=None):
        try:
            return zapi.call(zapi_method, params=params)
        except ZabbixAPIError as exc:
            data = exc.error.get('data')
            if data and ('already exists' in data or 'SQL statement execution has failed "INSERT INTO' in data):
                exc = RemoteObjectAlreadyExists(data)
            raise exc

    def _call_zapi(self, zapi_method, params=None):
        return self.call_zapi(self._zapi, zapi_method, params=params)

    @staticmethod
    def parse_zabbix_get_result(*args, **kwargs):
        kwargs['from_get_request'] = True
        return parse_zabbix_result(*args, **kwargs)

    @staticmethod
    def parse_zabbix_create_result(*args, **kwargs):
        kwargs['from_get_request'] = False
        return parse_zabbix_result(*args, **kwargs)

    @staticmethod
    def parse_zabbix_update_result(*args, **kwargs):
        kwargs['from_get_request'] = False
        return parse_zabbix_result(*args, **kwargs)

    @staticmethod
    def parse_zabbix_delete_result(*args, **kwargs):
        kwargs['from_get_request'] = False
        return parse_zabbix_result(*args, **kwargs)

    # noinspection PyUnusedLocal
    @staticmethod
    def trans_noop(value, from_zabbix=False, **kwargs):
        return value

    # noinspection PyUnusedLocal
    @staticmethod
    def trans_bool(value, from_zabbix=False, **kwargs):
        if from_zabbix:
            return bool(int(value))  # '1' -> True, '0' -> False
        else:
            return int(value)  # True -> 1, False -> 0

    # noinspection PyUnusedLocal
    @classmethod
    def trans_dc_qualified_name(cls, name, dc_name=None, from_zabbix=False, **kwargs):
        if from_zabbix:
            match = cls.RE_NAME_WITH_DC_PREFIX.match(name)

            if match:
                return match.group('name')
            else:
                return name
        else:
            assert dc_name, 'dc_name is a required parameter for translation to zabbix'
            return cls.TEMPLATE_NAME_WITH_DC_PREFIX.format(dc_name=dc_name, name=name)
