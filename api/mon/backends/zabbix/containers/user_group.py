from frozendict import frozendict

from que.tasks import get_task_logger
from api.mon.backends.zabbix.exceptions import (RemoteObjectManipulationError, RemoteObjectDoesNotExist,
                                                RemoteObjectAlreadyExists)
from api.mon.backends.zabbix.containers.base import ZabbixBaseContainer

task_logger = get_task_logger(__name__)


class ZabbixUserGroupContainer(ZabbixBaseContainer):
    """
    Container class for the Zabbix UserGroup object.
    """
    ZABBIX_ID_ATTR = 'usrgrpid'
    FRONTEND_ACCESS_ENABLED_WITH_DEFAULT_AUTH = '0'
    FRONTEND_ACCESS_DISABLED = '2'
    USERS_STATUS_ENABLED = 0
    PERMISSION_DENY = 0
    PERMISSION_READ_ONLY = 2
    PERMISSION_READ_WRITE = 3
    QUERY_BASE = frozendict({'selectUsers': ['alias'], 'selectRights': 'extend'})
    QUERY_WITHOUT_USERS = frozendict({'selectRights': 'extend'})
    OWNERS_GROUP = '#owner'
    NAME_MAX_LENGTH = 64
    AFFECTED_USERS = frozendict({
        ZabbixBaseContainer.NOTHING: frozenset(),
        ZabbixBaseContainer.CREATED: frozenset(),
        ZabbixBaseContainer.UPDATED: frozenset(),
        ZabbixBaseContainer.DELETED: frozenset(),
    })

    # noinspection PyUnresolvedReferences
    def __init__(self, *args, **kwargs):
        super(ZabbixUserGroupContainer, self).__init__(*args, **kwargs)
        self.users = set()  # type: [ZabbixUserContainer]  # noqa: F821
        self.hostgroup_ids = set()  # type: [int]
        self.superuser_group = False
        self.affected_users = frozendict({key: set() for key in self.AFFECTED_USERS})

    @classmethod
    def user_group_name_factory(cls, dc_name, local_group_name):
        """
        We have to qualify the dc name to prevent name clashing among groups in different datacenters,
        but in the same zabbix.
        """
        name = cls.trans_dc_qualified_name(local_group_name, dc_name)

        if len(name) > cls.NAME_MAX_LENGTH:
            raise ValueError('dc_name + group name should have less than 61 chars, '
                             'but they have %d instead: %s %s' % (len(name), dc_name, local_group_name))

        return name

    @classmethod
    def from_zabbix_data(cls, zapi, zabbix_object):
        from api.mon.backends.zabbix.containers.user import ZabbixUserContainer

        container = cls(zabbix_object['name'], zapi=zapi, zabbix_object=zabbix_object)
        #  container.superuser_group = FIXME cannot determine from this data
        container.users = {ZabbixUserContainer.from_zabbix_data(zapi, userdata)
                           for userdata in zabbix_object.get('users', [])}
        container.hostgroup_ids = {int(right['id']) for right in zabbix_object.get('rights', [])}

        return container

    @classmethod
    def from_zabbix_ids(cls, zapi, zabbix_ids, resolve_users=True):
        if resolve_users:
            query = cls.QUERY_BASE
        else:
            query = cls.QUERY_WITHOUT_USERS

        params = dict(usrgrpids=zabbix_ids, **query)
        response = cls.call_zapi(zapi, 'usergroup.get', params=params)

        return [cls.from_zabbix_data(zapi, item) for item in response]

    @classmethod
    def from_zabbix_name(cls, zapi, name, resolve_users=True):
        if resolve_users:
            query = cls.QUERY_BASE
        else:
            query = cls.QUERY_WITHOUT_USERS

        params = dict(filter={'name': name}, **query)
        response = cls.call_zapi(zapi, 'usergroup.get', params=params)
        zabbix_object = cls.parse_zabbix_get_result(response)

        return cls.from_zabbix_data(zapi, zabbix_object)

    @classmethod
    def from_mgmt_data(cls, zapi, dc_name, group_name, users, superusers=False):
        from api.mon.backends.zabbix.containers.user import ZabbixUserContainer
        from api.mon.backends.zabbix.containers.host_group import ZabbixHostGroupContainer

        # I should probably get all existing user ids for user names, and hostgroup ids for hostgroup names
        container = cls(group_name, zapi=zapi)
        container.users = {ZabbixUserContainer.from_mgmt_data(zapi, user) for user in users}
        container.hostgroup_ids = {zgc.zabbix_id for zgc in ZabbixHostGroupContainer.all(zapi, dc_name)}
        container.superuser_group = superusers  # FIXME this information is not used anywhere by now

        return container

    @classmethod
    def all(cls, zapi, dc_name, resolve_users=True):
        if resolve_users:
            query = cls.QUERY_BASE
        else:
            query = cls.QUERY_WITHOUT_USERS

        params = dict(
            search={'name': cls.TEMPLATE_NAME_WITH_DC_PREFIX.format(dc_name=dc_name, name='*')},
            searchWildcardsEnabled=True,
            **query
        )
        response = cls.call_zapi(zapi, 'usergroup.get', params=params)

        return [cls.from_zabbix_data(zapi, item) for item in response]

    @classmethod
    def synchronize(cls, zapi, dc_name, group_name, users, superusers=False):
        """
        Make sure that in the end, there will be a user group with specified users in zabbix.
        :param group_name: should be the qualified group name (<DC>:<group name>:)
        """
        # TODO synchronization of superadmins should be in the DC settings
        user_group = cls.from_mgmt_data(zapi, dc_name, group_name, users,  superusers=superusers)

        try:
            zabbix_user_group = cls.from_zabbix_name(zapi, group_name, resolve_users=True)
        except RemoteObjectDoesNotExist:
            # We create it
            return user_group.create()
        else:
            # Otherwise we update it
            return zabbix_user_group.update_from(user_group)

    @classmethod
    def delete_by_name(cls, zapi, name):
        # for optimization: z.zapi.usergroup.get({'search': {'name': ":dc_name:*"}, 'searchWildcardsEnabled': True})
        try:
            group = cls.from_zabbix_name(zapi, name)
        except RemoteObjectDoesNotExist:
            return cls.NOTHING, cls.AFFECTED_USERS
        else:
            return group.delete()

    @classmethod
    def _generate_hostgroup_rights(cls, hostgroup_ids):
        return [{
            'id': hostgroup_zabbix_id,
            'permission': cls.PERMISSION_READ_ONLY,
        } for hostgroup_zabbix_id in hostgroup_ids]

    def delete(self):
        task_logger.debug('Going to delete group %s', self.name)
        task_logger.debug('Group.users before: %s', self.users)
        users_to_remove = self.users.copy()  # We have to copy it because group.users will get messed up
        self.remove_users(users_to_remove, delete_users_if_last=True)  # remove all users
        task_logger.debug('Group.users after: %s', self.users)
        self._api_response = self._call_zapi('usergroup.delete', params=[self.zabbix_id])
        self.parse_zabbix_delete_result(self._api_response, 'usrgrpids')
        self.reset()

        return self.DELETED, self.affected_users

    def create(self):
        assert not self.zabbix_id, \
            '%s has the zabbix_id already and therefore you should try to update the object, not create it.' % self

        user_group_object = {
            'name': self.name,
            'users_status': self.USERS_STATUS_ENABLED,
            'gui_access': self.FRONTEND_ACCESS_DISABLED,
            'rights': self._generate_hostgroup_rights(self.hostgroup_ids),
        }

        task_logger.debug('Creating usergroup: %s', user_group_object)
        self._api_response = self._call_zapi('usergroup.create', params=user_group_object)
        self.zabbix_id = int(self.parse_zabbix_create_result(self._api_response, 'usrgrpids'))
        user_group_object['userids'] = []
        self._refetch_users()
        self._push_current_users()

        return self.CREATED, self.affected_users

    def _refresh_users(self):
        from api.mon.backends.zabbix.containers.user import ZabbixUserContainer

        self.users = {
            ZabbixUserContainer.from_zabbix_data(self._zapi, userdata)
            for userdata in self.zabbix_object.get('users', [])
        }

    def refresh(self):
        params = dict(usrgrpids=self.zabbix_id, **self.QUERY_BASE)
        self._api_response = self._call_zapi('usergroup.get', params=params)
        zabbix_object = self.parse_zabbix_get_result(self._api_response)
        self.init(zabbix_object)
        self._refresh_users()

    def update_users(self, user_group):
        task_logger.debug('synchronizing %s', self)
        task_logger.debug('remote_user_group.users %s', self.users)
        task_logger.debug('source_user_group.users %s', user_group.users)
        redundant_users = self.users - user_group.users
        task_logger.debug('redundant_users: %s', redundant_users)
        missing_users = user_group.users - self.users
        task_logger.debug('missing users: %s', missing_users)
        self.remove_users(redundant_users, delete_users_if_last=True)
        self.add_users(missing_users)

    def set_hostgroup_rights(self, new_hostgroup_ids):
        task_logger.debug('setting usergroup %s hostgroups rights to: %s', self, new_hostgroup_ids)
        params = dict(usrgrpid=self.zabbix_id, rights=self._generate_hostgroup_rights(new_hostgroup_ids))
        self._api_response = self._call_zapi('usergroup.update', params=params)
        self.parse_zabbix_update_result(self._api_response, 'usrgrpids')
        self.hostgroup_ids = new_hostgroup_ids

    def add_hostgroup_right(self, hostgroup_id):
        if hostgroup_id not in self.hostgroup_ids:
            hostgroup_ids = self.hostgroup_ids.copy()
            hostgroup_ids.add(hostgroup_id)
            self.set_hostgroup_rights(hostgroup_ids)

    def update_from(self, user_group):
        self.update_users(user_group)

        if self.hostgroup_ids != user_group.hostgroup_ids:
            self.set_hostgroup_rights(user_group.hostgroup_ids)

        return self.UPDATED, self.affected_users

    def _refetch_users(self):
        for user in self.users:
            user.renew_zabbix_id()
            user.groups.add(self)

            if not user.zabbix_id:
                try:
                    user.create()
                except RemoteObjectAlreadyExists:
                    user.renew_zabbix_id()
                else:
                    self.affected_users[self.CREATED].add(user.name)

    def add_users(self, new_users):
        self.users.update(new_users)
        self._refetch_users()
        self._push_current_users()

    def _push_current_users(self):
        self._call_zapi('usergroup.update', params={
            'usrgrpid': self.zabbix_id,
            'userids': [user.zabbix_id for user in self.users]
        })
        self.affected_users[self.UPDATED].update(user.name for user in self.users)

    def remove_user(self, user, delete_user_if_last=False):
        user.refresh()

        if self not in user.groups:
            task_logger.warn('User is not in the group: %s %s (possible race condition)', self, user.groups)

        if not user.groups - {self} and not delete_user_if_last:
            raise RemoteObjectManipulationError('Cannot remove the last group (%s) '
                                                'without deleting the user %s itself!' % (self, user))

        user.groups -= {self}

        if user.groups:
            user.update_group_membership()
            res = self.UPDATED
        else:
            user.delete()
            res = self.DELETED

        self.affected_users[res].add(user.name)

        return res

    def remove_users(self, redundant_users, delete_users_if_last):  # TODO move
        self.users -= redundant_users
        # Some zabbix users have to be deleted as this is their last group. We have to go the slower way.
        for user in redundant_users:
            self.remove_user(user, delete_user_if_last=delete_users_if_last)
            # TODO create also a faster way of removal for users that have also different groups

    @property
    def name_without_dc_prefix(self):
        return self.trans_dc_qualified_name(self.name, from_zabbix=True)

    @property
    def as_mgmt_data(self):
        return {'id': self.zabbix_id, 'name': self.name_without_dc_prefix}
