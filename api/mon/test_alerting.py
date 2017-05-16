from api.mon.zabbix import getZabbix, ZabbixUserGroupContainer, ZabbixUserContainer
from vms.models import Dc
from gui.models import User
from unittest import TestCase


class TestUsergroupManipulation(TestCase):
    zabbix = None

    def setUp(self):
        self.zabbix = getZabbix(Dc.objects.all()[0]).izx
        assert User.objects.count()>5,"you have to have at least 5 users in the database to run tests"

    def test_user_manipulation(self):
        # create users and group
        # test_create_users_and_user_group(5,'pirati')
        # raw_input('group pirati should exist and should have 5 members')
        # delete users
        group_name = 'tgroup1'
        member_count = 3
        ug = self._create_users_and_user_group(member_count, group_name)
        # create second group
        second_group_name = 'ufonci'
        second_group_member_count = 2
        self._create_users_and_user_group(second_group_member_count, second_group_name)

        assert self._get_user_group_user_count(second_group_name) == second_group_member_count
        assert self._get_user_group_user_count(group_name) == member_count

        increased_second_group_member_count = 4
        self._create_users_and_user_group(increased_second_group_member_count, second_group_name)

        assert self._get_user_group_user_count(second_group_name) == increased_second_group_member_count
        assert self._get_user_group_user_count(group_name) == member_count

        decreased_second_group_member_count = 1
        self._create_users_and_user_group(decreased_second_group_member_count, second_group_name)

        assert self._get_user_group_user_count(second_group_name) == decreased_second_group_member_count
        assert self._get_user_group_user_count(group_name) == member_count

        self.zabbix.delete_user_group(group_name=second_group_name)
        assert self._get_user_group_user_count(group_name) == member_count

        increased_second_group_member_count = 4
        self._create_users_and_user_group(increased_second_group_member_count, second_group_name)
        assert self._get_user_group_user_count(second_group_name) == increased_second_group_member_count
        assert self._get_user_group_user_count(group_name) == member_count

        self.zabbix.delete_user_group(group_name=group_name)
        assert self._get_user_group_user_count(second_group_name) == increased_second_group_member_count

        self.zabbix.delete_user_group(group_name=second_group_name)

    def _get_user_group_user_count(self, group_name):
        first_group = self.zabbix.zapi.usergroup.get({'search': {'name': group_name},
                                                      'selectUsers': ['alias'],
                                                      'limit': 1})[0]
        return len(first_group.get('users', []))

    def _create_users_and_user_group(self, user_count=5, name='pirati'):
        users = User.objects.all()[:user_count]
        ug = self.zabbix.synchronize_user_group(name, users, [])
        return ug

    def _create_user_group(self, group_name, users=()):
        ugc = ZabbixUserGroupContainer.from_mgmt_data(self.zabbix.zapi, group_name, users)
        ugc.to_zabbix(True, True, True)
        return ugc

    def test_create_delete_empty_user_group(self, dc_name='dc', user_group_name='abc'):
        zabbix_user_group_name = ZabbixUserGroupContainer.user_group_name_factory(dc_name, user_group_name)
        self._create_user_group(zabbix_user_group_name)
        response = self.zabbix.zapi.usergroup.get({'search': {'name': zabbix_user_group_name}})
        assert response and len(
            response) == 1, 'there should be one and only one user_group %s created' % zabbix_user_group_name
        zugc = ZabbixUserGroupContainer.from_zabbix_data(self.zabbix.zapi, response[0])
        self.zabbix.delete_user_group(zabbix_id=zugc.zabbix_id)
        response = self.zabbix.zapi.usergroup.get({'search': {'name': zabbix_user_group_name}})
        assert not response, "group should have been deleted"

    def test_create_delete_user(self):
        # we have to create user group first
        group_name = 'abcd'
        g = self._create_user_group(group_name)

        db_user = User.objects.all()[0]
        user = ZabbixUserContainer.from_mgmt_data(self.zabbix.zapi, db_user)
        assert not user.zabbix_id
        user.groups.add(g)
        user.to_zabbix(True, True, True)
        assert user.zabbix_id
        users_id = user.zabbix_id
        same_user = ZabbixUserContainer.from_zabbix_alias(self.zabbix.zapi, db_user.username)
        assert same_user == user
        self.zabbix.delete_user(user)
        self.assertRaises(Exception, ZabbixUserContainer.from_zabbix_alias, self.zabbix.zapi, db_user.username)
        self.assertRaises(Exception, ZabbixUserContainer.from_zabbix_id, self.zabbix.zapi, users_id)

        # and cleanup
        self.zabbix.delete_user_group(zabbix_id=g.zabbix_id)

    def test_create_update_delete_group_with_users(self):
        group_name = 'tgroup1'
        member_count = 3
        ug = self._create_users_and_user_group(member_count, group_name)
        response = self.zabbix.zapi.usergroup.get({'search': {'name': group_name},
                                                   'selectUsers': ['alias'],
                                                   'limit': 1})
        assert response, 'group should have been created in zabbix'
        zabbix_group = response[0]
        assert zabbix_group.get('name', '') == group_name, ' zabbix group should have the same name as we defined'
        assert len(
            zabbix_group.get('users', [])) == member_count, 'the group should have exactly %d members' % member_count

        # update group
        increased_member_count = 4
        self._create_users_and_user_group(increased_member_count, group_name)
        response = self.zabbix.zapi.usergroup.get({'search': {'name': group_name},
                                                   'selectUsers': ['alias'],
                                                   'limit': 1})
        zabbix_group = response[0]
        assert len(
            zabbix_group.get('users',
                             [])) == increased_member_count, 'the group should have exactly %d members' % increased_member_count
        zugc = ZabbixUserGroupContainer.from_zabbix_data(self.zabbix.zapi, zabbix_group)
        self.zabbix.delete_user_group(group=zugc)
        response = self.zabbix.zapi.usergroup.get({'search': {'name': group_name}})
        assert not response
