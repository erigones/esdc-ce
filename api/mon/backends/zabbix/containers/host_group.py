from frozendict import frozendict

from api.decorators import lock
from api.mon.backends.zabbix.exceptions import (RemoteObjectDoesNotExist, RemoteObjectAlreadyExists,
                                                RemoteObjectManipulationError)
from api.mon.backends.zabbix.containers.base import ZabbixBaseContainer


class ZabbixHostGroupContainer(ZabbixBaseContainer):
    """
    Container class for the Zabbix HostGroup object.
    """
    ZABBIX_ID_ATTR = 'groupid'
    NAME_MAX_LENGTH = 64
    QUERY_BASE = frozendict({'output': ['name', 'groupid'], 'selectHosts': 'count'})
    new = False

    @classmethod
    def hostgroup_name_factory(cls, dc_name, hostgroup_name):
        if dc_name:  # local hostgroup
            name = cls.trans_dc_qualified_name(hostgroup_name, dc_name)

            if len(name) > cls.NAME_MAX_LENGTH:
                raise ValueError('dc_name + group name should have less than 61 chars, '
                                 'but they have %d instead: %s %s' % (len(name), dc_name, hostgroup_name))
        else:
            name = hostgroup_name  # global hostgroup

        return name

    @classmethod
    def from_mgmt_data(cls, zapi, name):
        return cls(name, zapi=zapi)

    @classmethod
    def from_zabbix_name(cls, zapi, name):
        container = cls(name, zapi=zapi)
        container.refresh()

        return container

    @classmethod
    def from_zabbix_data(cls, zapi, zabbix_object):
        return cls(zabbix_object['name'], zapi=zapi, zabbix_object=zabbix_object)

    @classmethod
    def from_zabbix_ids(cls, zapi, zabbix_ids):
        params = dict({'groupids': zabbix_ids}, **cls.QUERY_BASE)
        response = cls.call_zapi(zapi, 'hostgroup.get', params=params)

        return [cls.from_zabbix_data(zapi, item) for item in response]

    @classmethod
    def _is_visible_from_dc(cls, zabbix_object, dc_name):
        match = cls.RE_NAME_WITH_DC_PREFIX.match(zabbix_object['name'])

        if match:
            # RE_NAME_WITH_DC_PREFIX results in exactly two (named) groups: dc name and hostgroup name:
            return match.group('dc_name') == dc_name
        else:
            return True

    @classmethod
    def all(cls, zapi, dc_name=None):
        response = cls.call_zapi(zapi, 'hostgroup.get', params=dict(cls.QUERY_BASE))

        if dc_name is not None:
            response = (hostgroup for hostgroup in response if cls._is_visible_from_dc(hostgroup, dc_name))

        return [cls.from_zabbix_data(zapi, item) for item in response]

    @classmethod
    def _clear_hostgroup_list_cache(cls, name):
        from api.mon.base.api_views import MonHostgroupView
        # Invalidate cache for mon_hostgroup_list only if we have dc_name
        match = cls.RE_NAME_WITH_DC_PREFIX.match(name)

        if match:
            dc_name = match.group('dc_name')

            for dc_bound in (True, False):
                for full in (True, False):
                    MonHostgroupView.clear_cache(dc_name, dc_bound, full=full)

    def refresh(self):
        params = dict(filter={'name': self.name}, **self.QUERY_BASE)
        self._api_response = self._call_zapi('hostgroup.get', params=params)
        zabbix_object = self.parse_zabbix_get_result(self._api_response)
        self.init(zabbix_object)

    def create(self):
        params = {'name': self.name}
        self._api_response = self._call_zapi('hostgroup.create', params=params)
        self.zabbix_id = int(self.parse_zabbix_create_result(self._api_response, 'groupids'))
        self.zabbix_object = params
        # Invalidate cache for mon_hostgroup_list
        self._clear_hostgroup_list_cache(self.name)
        self.new = True

        return self.CREATED

    @classmethod
    @lock(key_args=(1,), wait_for_release=True, bound=True)
    def create_from_name(cls, zapi, name):
        container = cls(name, zapi=zapi)

        try:
            container.create()
        except RemoteObjectAlreadyExists:
            container.refresh()

        return container

    @classmethod
    def get_or_create(cls, zapi, name):
        try:
            return ZabbixHostGroupContainer.from_zabbix_name(zapi, name)
        except RemoteObjectDoesNotExist:
            return ZabbixHostGroupContainer.create_from_name(zapi, name)

    def delete(self):
        assert self.zabbix_id, 'Cannot delete Hostgroup without groupid'

        if int(self.zabbix_object.get('hosts', 0)):
            # TODO: empty
            raise RemoteObjectManipulationError('Monitoring hostgroup is not empty')

        self._api_response = self._call_zapi('hostgroup.delete', params=[self.zabbix_id])
        assert self.zabbix_id == int(self.parse_zabbix_delete_result(self._api_response, 'groupids'))
        self.reset()
        # Invalidate cache for mon_hostgroup_list
        self._clear_hostgroup_list_cache(self.name)

        return self.DELETED

    @property
    def name_without_dc_prefix(self):
        return self.trans_dc_qualified_name(self.name, from_zabbix=True)

    @property
    def as_mgmt_data(self):
        match = self.RE_NAME_WITH_DC_PREFIX.match(self.name)

        if match:
            name = match.group('name')
            hosts = int(self.zabbix_object.get('hosts', 0))
        else:
            # Hide host count for non-local hostgroup
            name = self.name
            hosts = None

        return {
            'id': self.zabbix_id,
            'name': name,
            'hosts': hosts,
            'global': not bool(match),
        }
