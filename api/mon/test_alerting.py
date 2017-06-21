from unittest import TestCase

from django.utils.crypto import get_random_string
from zabbix_api import ZabbixAPIError

from api.mon.backends.zabbix.base import ZabbixUserGroupContainer
from api.mon.backends.zabbix import get_monitoring
from vms.models import Dc
from gui.models import User, Role


class AlertingAPIAdapterTests(TestCase):
    dc = None
    zabbix = None
    db_users = None
    db_groups = None

    def setUp(self):
        self.dc = Dc.objects.all()[0]
        self.zabbix = get_monitoring(self.dc)

        self.db_users = []
        self.db_groups = []
        for x in range(5):
            self.db_users.append(self._create_db_user())
        for x in range(5):
            self.db_groups.append(self._create_db_group())

    def tearDown(self):
        for user in self.db_users:
            try:
                self.zabbix.delete_user(name=user.username)
            except ZabbixAPIError:
                pass
            user.delete()
        for group in self.db_groups:
            try:
                self.zabbix.delete_user_group(name=group.name)
            except ZabbixAPIError:
                pass
            group.delete()

    def _create_db_user(self):
        user = User()
        user.first_name = get_random_string(10)
        user.last_name = get_random_string(10)
        user.api_access = True
        user.is_active = True
        user.is_super_admin = False
        user.callback_key = '***'
        user.password = get_random_string(10)
        user.email = get_random_string(10) + '@' + get_random_string(10) + '.com'
        user.api_key = get_random_string(30)
        user.username = 'Test' + get_random_string(10)
        user.password = get_random_string(10)
        user.save()
        return user

    def _create_db_group(self):
        group = Role()
        group.name = 'TestN' + get_random_string(10)
        group.alias = 'TestA' + get_random_string(10)
        group.save()
        group.dc_set.add(self.dc)
        assert self.dc in Role.objects.filter(name=group.name).first().dc_set.all()
        return group

    def _get_user_group_user_count(self, group_name):
        first_group = self.zabbix.izx.zapi.usergroup.get({'search': {'name': group_name}, 'selectUsers': ['alias']})[0]
        return len(first_group.get('users', []))

    def _create_zabbix_user_group(self, group):
        self.assertListEqual(self.zabbix.izx.zapi.usergroup.get(
            {'search': {'name': ZabbixUserGroupContainer.user_group_name_factory(self.dc.name, group.name)}
             }), [], 'the group should not exist')
        self.zabbix.synchronize_user_group(group=group)
        self.assertEqual(len(self.zabbix.izx.zapi.usergroup.get(
            {'search': {'name': ZabbixUserGroupContainer.user_group_name_factory(self.dc.name, group.name)}
             })), 1, 'the group should be in zabbix by now')

    def _create_zabbix_user(self, db_user):
        self.assertListEqual(self.zabbix.izx.zapi.user.get(dict(filter={'alias': db_user.username})), [],
                             'user shouldn\'t be in zabbix before creation')
        self.zabbix.synchronize_user(db_user)
        self.assertEqual(len(self.zabbix.izx.zapi.user.get(dict(filter={'alias': db_user.username}))), 1,
                         'user should be in zabbix by now')

    def test_create_delete_empty_user_group(self):
        db_group = self.db_groups[0]
        self._create_zabbix_user_group(db_group)

        self.zabbix.delete_user_group(db_group.name)

        self.assertListEqual(self.zabbix.izx.zapi.usergroup.get({'search': {'name': db_group.name}, 'limit': 1}), [],
                             'the group shouldn\'t exist anymore')

    def test_create_delete_user(self):
        # we have to create user group first
        db_group = self.db_groups[0]

        self._create_zabbix_user_group(db_group)

        db_user = self.db_users[0]
        self.assertRaises(Exception, self.zabbix.synchronize_user, (db_user,),
                          'it should not be permitted to create user without group')

        db_user.roles.add(db_group)
        self._create_zabbix_user(db_user)

        self.zabbix.delete_user(db_user.username)

        self.assertListEqual(self.zabbix.izx.zapi.user.get(dict(filter={'alias': db_user.username})), [],
                             'user shouldn\'t be in zabbix anymore')

        self.zabbix.delete_user_group(db_group.name)

    def _test_user_group_manipulation(self):
        raise NotImplementedError()  # TODO

    def _test_user_manipulation(self):
        # user added to a group
        # user removed from a group
        # user media changed
        # user media deleted
        # user admin status changed for a dc
        # dc ownership changed
        raise NotImplementedError()  # TODO
