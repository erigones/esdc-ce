from unittest import TestCase

from django.utils.crypto import get_random_string
from django.conf import settings

from api.mon.backends.zabbix import get_monitoring
from api.mon.backends.zabbix.exceptions import (MonitoringError, RemoteObjectDoesNotExist, RemoteObjectAlreadyExists,
                                                RelatedRemoteObjectDoesNotExist)
from api.mon.backends.zabbix.containers import (ZabbixUserGroupContainer, ZabbixMediaContainer,
                                                ZabbixHostGroupContainer, ZabbixActionContainer)
from vms.models import Dc
from gui.models import User, Role


class ZabbixAPIAdapterTests(TestCase):
    """
    These tests are designed to run in one and only one DC.
    """
    # noinspection PyMethodMayBeStatic
    def _create_db_user(self):
        user = User()
        user.first_name = get_random_string(10)
        user.last_name = get_random_string(10)
        user.api_access = True
        user.is_active = True
        user.is_staff = False
        user.password = get_random_string(10)
        user.email = get_random_string(10) + '@' + get_random_string(10) + '.com'
        user.username = 'Test_' + get_random_string(10)
        user.password = get_random_string(10)
        user.save()
        user.userprofile.alerting_email = user.email
        user.userprofile.alerting_phone = get_random_string(10)
        user.userprofile.alerting_jabber = 'jabber_' + user.email
        user.userprofile.save()
        return user

    def _create_db_group(self):
        group = Role()
        group.name = 'Group_N' + get_random_string(10)
        group.alias = 'Group_A' + get_random_string(10)
        group.save()
        group.dc_set.add(self.dc)
        assert self.dc in Role.objects.filter(name=group.name).first().dc_set.all()
        return group

    # noinspection PyMethodMayBeStatic
    def _create_dc(self):
        dc = Dc()
        dc.name = 'DC_' + get_random_string(10)
        dc.alias = dc.name
        dc.owner = User.objects.get(id=settings.ADMIN_USER)
        dc.site = get_random_string(10)
        dc.save()
        return dc

    def setUp(self):
        self.dc = self._create_dc()
        self.zabbix = get_monitoring(self.dc)
        self.ezx_zapi = self.zabbix.ezx.zapi
        self.db_users = []
        self.db_groups = []
        self.hostgroups = []
        self.actions = []

        for x in range(5):
            self.db_users.append(self._create_db_user())
        for x in range(5):
            self.db_groups.append(self._create_db_group())
        for x in range(5):
            self.hostgroups.append(get_random_string(10))
        for x in range(5):
            self.actions.append(get_random_string(10))

    def tearDown(self):
        for user in self.db_users:
            try:
                self.zabbix.user_delete(name=user.username)
            except MonitoringError:
                pass
            user.delete()

        for group in self.db_groups:
            try:
                self.zabbix.user_group_delete(name=group.name)
            except MonitoringError:
                pass
            group.delete()

        for hostgroup in self.hostgroups:
            try:
                self.zabbix.hostgroup_delete(hostgroup)
            except MonitoringError:
                pass

        for action_name in self.actions:
            try:
                self.zabbix.action_delete(action_name)
            except MonitoringError:
                pass

        self.dc.delete()

    def _get_zabbix_user(self, db_user):
        return self.ezx_zapi.user.get(dict(filter={'alias': db_user.username}, selectMedias='extend',
                                      selectUsrgrps='extend', selectMediatypes='extend'))[0]

    def _check_user_media(self, db_user, zabbix_user):
        zabbix_user_medias = {}  # {media_type_desc: sendto}

        for media_type in zabbix_user.get('mediatypes', []):
            for media in zabbix_user.get('medias', []):
                if media_type['mediatypeid'] == media['mediatypeid']:
                    zabbix_user_medias[media_type['description']] = media['sendto']

        for media_type in ZabbixMediaContainer.MEDIA_TYPES:
            wanted_user_media_sendto = ZabbixMediaContainer.extract_sendto_from_user(media_type, db_user)
            media_type_desc = ZabbixMediaContainer.get_media_type_desc(media_type, dc_settings=self.dc.settings)

            if wanted_user_media_sendto and media_type_desc:
                self.assertEqual(zabbix_user_medias.get(media_type_desc, None), wanted_user_media_sendto,
                                 "user's media type={} sendto={} should be in zabbix".format(media_type,
                                                                                             wanted_user_media_sendto))
            elif media_type_desc:
                self.assertNotIn(media_type_desc, zabbix_user_medias,
                                 'user should not have media type={} in zabbix'.format(media_type))
            elif wanted_user_media_sendto:
                self.assertNotIn(wanted_user_media_sendto, zabbix_user_medias.values(),
                                 'user should not have media type={} in zabbix'.format(media_type))
            else:
                raise AssertionError

    def _sync_zabbix_user_group(self, db_group, new=False, empty=False):
        if new:
            self.assertListEqual(self.ezx_zapi.usergroup.get({
                'search': {'name': ZabbixUserGroupContainer.user_group_name_factory(self.dc.name, db_group.name)}
            }), [], 'the group should not exist')

        self.zabbix.user_group_sync(group=db_group)
        zabbix_user_group_ = self.ezx_zapi.usergroup.get({
            'search': {'name': ZabbixUserGroupContainer.user_group_name_factory(self.dc.name, db_group.name)},
            'selectUsers': 'extend',
        })
        self.assertEqual(len(zabbix_user_group_), 1, 'the group should be in zabbix by now')
        zabbix_user_group = zabbix_user_group_[0]
        zabbix_user_group_users = {user['alias']: user for user in zabbix_user_group.get('users', [])}

        if empty:
            self.assertEquals(len(zabbix_user_group_users), 0, 'the group should be empty in zabbix')
            return

        for db_user in db_group.user_set.all():
            self.assertIn(db_user.username, zabbix_user_group_users,
                          'user should be member of the user group in zabbix')
            zabbix_user = self._get_zabbix_user(db_user)
            self.assertEquals(zabbix_user_group_users[db_user.username]['userid'], zabbix_user['userid'])
            self._check_user_media(db_user, zabbix_user)

    def _delete_zabbix_user_group(self, db_group, last_for_all_users=False):
        self.zabbix.user_group_delete(db_group.name)
        self.assertListEqual(self.ezx_zapi.usergroup.get({
            'search': {'name': ZabbixUserGroupContainer.user_group_name_factory(self.dc.name, db_group.name)},
            'limit': 1
        }), [], 'the group shouldn\'t exist anymore')

        if last_for_all_users:
            for db_user in db_group.user_set.all():
                self.assertListEqual(self.ezx_zapi.user.get(dict(filter={'alias': db_user.username})), [],
                                     'user shouldn\'t be in zabbix anymore')

    def _sync_zabbix_user(self, db_user, new=False):
        if new:
            self.assertListEqual(self.ezx_zapi.user.get(dict(filter={'alias': db_user.username})), [],
                                 'user shouldn\'t be in zabbix before creation')

        self.zabbix.user_sync(db_user)
        zabbix_user_ = self.ezx_zapi.user.get(dict(filter={'alias': db_user.username}, selectMedias='extend',
                                                   selectUsrgrps='extend', selectMediatypes='extend'))

        if not db_user.roles.exists():
            self.assertEqual(len(zabbix_user_), 0, 'user without groups should not exist in zabbix')
            return

        self.assertEqual(len(zabbix_user_), 1, 'user should be in zabbix by now')
        zabbix_user = zabbix_user_[0]
        zabbix_user_groups = set(group['name'] for group in zabbix_user.get('usrgrps', []))
        wanted_zabbix_user_groups = set(ZabbixUserGroupContainer.user_group_name_factory(self.dc.name, db_group.name)
                                        for db_group in db_user.roles.all())
        self.assertSetEqual(zabbix_user_groups, wanted_zabbix_user_groups, "user's groups in zabbix should "
                                                                           "match groups in DB")
        self._check_user_media(db_user, zabbix_user)

    def _delete_zabbix_user(self, db_user):
        self.zabbix.user_delete(db_user.username)
        self.assertListEqual(self.ezx_zapi.user.get(dict(filter={'alias': db_user.username})), [],
                             'user shouldn\'t be in zabbix anymore')

    def test_001_create_delete_user_group_empty(self):
        db_group = self.db_groups[0]
        self._sync_zabbix_user_group(db_group, new=True, empty=True)
        self._delete_zabbix_user_group(db_group, last_for_all_users=True)

    def test_002_create_delete_user(self):
        # we have to create user group first
        db_group = self.db_groups[0]
        self._sync_zabbix_user_group(db_group, new=True, empty=True)

        # user still without groups -> this should not create a user in zabbix
        db_user = self.db_users[0]
        self._sync_zabbix_user(db_user, new=True)

        db_user.roles.add(db_group)
        self._sync_zabbix_user(db_user, new=True)
        self._delete_zabbix_user(db_user)
        self._delete_zabbix_user_group(db_group, last_for_all_users=True)
        db_user.roles.remove(db_group)

    def test_003_create_delete_user_group_nonempty(self):
        # we have to create user group first
        db_group = self.db_groups[0]
        self._sync_zabbix_user_group(db_group, new=True, empty=True)

        db_users = self.db_users

        for user in db_users:
            user.roles.add(db_group)

        self._sync_zabbix_user_group(db_group, new=False, empty=False)
        self._delete_zabbix_user_group(db_group, last_for_all_users=True)

        for user in db_users:
            user.roles.remove(db_group)

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

    def _get_new_hostgroup(self, hostgroup_name, dc_bound=True):
        if dc_bound:
            dc_name = self.dc.name
        else:
            dc_name = None

        self.assertListEqual(self.ezx_zapi.hostgroup.get({
            'filter': {'name': ZabbixHostGroupContainer.hostgroup_name_factory(dc_name, hostgroup_name)}}
        ), [], 'hostgroup should not exist in zabbix')
        self.assertRaises(RemoteObjectDoesNotExist, self.zabbix.hostgroup_detail, hostgroup_name, dc_bound=dc_bound)

    def _get_existing_hostgroup(self, hostgroup_name, dc_bound=True):
        if dc_bound:
            dc_name = self.dc.name
        else:
            dc_name = None

        zabbix_hostgroup_ = self.ezx_zapi.hostgroup.get({
            'filter': {'name': ZabbixHostGroupContainer.hostgroup_name_factory(dc_name, hostgroup_name)}}
        )
        self.assertEqual(len(zabbix_hostgroup_), 1, 'hostgroup should exist in zabbix')
        hostgroup_info = self.zabbix.hostgroup_detail(hostgroup_name, dc_bound=dc_bound)
        self.assertEqual(hostgroup_info['name'], hostgroup_name)

    def _create_new_hostgroup(self, hostgroup_name, dc_bound=True):
        if dc_bound:
            dc_name = self.dc.name
        else:
            dc_name = None

        self.assertListEqual(self.ezx_zapi.hostgroup.get({
            'filter': {'name': ZabbixHostGroupContainer.hostgroup_name_factory(dc_name, hostgroup_name)}}
        ), [], 'hostgroup should not exist in zabbix')
        hostgroup_info = self.zabbix.hostgroup_create(hostgroup_name, dc_bound=dc_bound)
        zabbix_hostgroup_ = self.ezx_zapi.hostgroup.get({
            'filter': {'name': ZabbixHostGroupContainer.hostgroup_name_factory(dc_name, hostgroup_name)}}
        )
        self.assertEqual(len(zabbix_hostgroup_), 1, 'hostgroup should exist in zabbix')
        self.assertEqual(hostgroup_info['name'], hostgroup_name)

        return hostgroup_info

    def _create_existing_hostgroup(self, hostgroup_name, dc_bound=True):
        if dc_bound:
            dc_name = self.dc.name
        else:
            dc_name = None

        zabbix_hostgroup_ = self.ezx_zapi.hostgroup.get({
            'filter': {'name': ZabbixHostGroupContainer.hostgroup_name_factory(dc_name, hostgroup_name)}}
        )
        self.assertEqual(len(zabbix_hostgroup_), 1, 'hostgroup should exist in zabbix')
        self.assertRaises(RemoteObjectAlreadyExists, self.zabbix.hostgroup_create, hostgroup_name, dc_bound=dc_bound)

    def _delete_existing_hostgroup(self, hostgroup_name, dc_bound=True):
        if dc_bound:
            dc_name = self.dc.name
        else:
            dc_name = None

        self.zabbix.hostgroup_delete(hostgroup_name, dc_bound=dc_bound)
        self.assertListEqual(self.ezx_zapi.hostgroup.get({
            'filter': {'name': ZabbixHostGroupContainer.hostgroup_name_factory(dc_name, hostgroup_name)}}
        ), [], 'hostgroup should not exist in zabbix anymore')

    def _delete_new_hostgroup(self, hostgroup_name, dc_bound=True):
        if dc_bound:
            dc_name = self.dc.name
        else:
            dc_name = None

        self.assertListEqual(self.ezx_zapi.hostgroup.get({
            'filter': {'name': ZabbixHostGroupContainer.hostgroup_name_factory(dc_name, hostgroup_name)}}
        ), [], 'hostgroup should not exist in zabbix anymore')
        self.assertRaises(RemoteObjectDoesNotExist, self.zabbix.hostgroup_delete, hostgroup_name, dc_bound=dc_bound)

    def test_101_create_get_delete_hostgroup(self):
        hostgroup = self.hostgroups[0]
        self._create_new_hostgroup(hostgroup)
        self._get_existing_hostgroup(hostgroup)
        self._delete_existing_hostgroup(hostgroup)

        self._create_new_hostgroup(hostgroup, dc_bound=False)
        self._get_existing_hostgroup(hostgroup, dc_bound=False)
        self._delete_existing_hostgroup(hostgroup, dc_bound=False)

    def test_102_create_delete_existing_hostgroup(self):
        hostgroup = self.hostgroups[0]
        self._create_new_hostgroup(hostgroup)
        self._create_existing_hostgroup(hostgroup)
        self._delete_existing_hostgroup(hostgroup)

        self._create_new_hostgroup(hostgroup, dc_bound=False)
        self._create_existing_hostgroup(hostgroup, dc_bound=False)
        self._delete_existing_hostgroup(hostgroup, dc_bound=False)

    def test_103_delete_new_hostgroup(self):
        hostgroup = self.hostgroups[0]
        self._delete_new_hostgroup(hostgroup)
        self._delete_new_hostgroup(hostgroup, dc_bound=False)

    def test_104_get_new_hostgroup(self):
        hostgroup = self.hostgroups[0]
        self._get_new_hostgroup(hostgroup)
        self._get_new_hostgroup(hostgroup, dc_bound=False)

    def _get_new_action(self, action_name):
        self.assertListEqual(self.ezx_zapi.action.get({
            'filter': {'name': ZabbixActionContainer.action_name_factory(self.dc.name, action_name)}}
        ), [], 'action should not exist in zabbix')
        self.assertRaises(RemoteObjectDoesNotExist, self.zabbix.action_detail, action_name)

    def _get_existing_action(self, action_name):
        zabbix_action_ = self.ezx_zapi.action.get({
            'filter': {'name': ZabbixActionContainer.action_name_factory(self.dc.name, action_name)}}
        )
        self.assertEqual(len(zabbix_action_), 1, 'action should exist in zabbix')
        action_info = self.zabbix.action_detail(action_name)
        self.assertEqual(action_info['name'], action_name)

        return action_info

    def _create_new_action(self, action_name, action_data, nonexistent_usergroups=False):
        self.assertListEqual(self.ezx_zapi.action.get({
            'filter': {'name': ZabbixActionContainer.action_name_factory(self.dc.name, action_name)}}
        ), [], 'action should not exist in zabbix')

        if nonexistent_usergroups:
            self.assertRaises(RelatedRemoteObjectDoesNotExist, self.zabbix.action_create, action_name, action_data)
            return

        action_info = self.zabbix.action_create(action_name, action_data)
        zabbix_action_ = self.ezx_zapi.action.get({
            'filter': {'name': ZabbixActionContainer.action_name_factory(self.dc.name, action_name)}}
        )
        self.assertEqual(len(zabbix_action_), 1, 'action should exist in zabbix')
        self.assertEqual(action_info['name'], action_name)

        return action_info

    def _create_existing_action(self, action_name, action_data):
        zabbix_action_ = self.ezx_zapi.action.get({
            'filter': {'name': ZabbixActionContainer.action_name_factory(self.dc.name, action_name)}}
        )
        self.assertEqual(len(zabbix_action_), 1, 'action should exist in zabbix')
        self.assertRaises(RemoteObjectAlreadyExists, self.zabbix.action_create, action_name, action_data)

    def _update_new_action(self, action_name, action_data):
        self.assertListEqual(self.ezx_zapi.action.get({
            'filter': {'name': ZabbixActionContainer.action_name_factory(self.dc.name, action_name)}}
        ), [], 'action should not exist in zabbix')
        self.assertRaises(RemoteObjectDoesNotExist, self.zabbix.action_update, action_name, action_data)

    def _update_existing_action(self, action_name, action_data, nonexistent_usergroups=False):
        zabbix_action_ = self.ezx_zapi.action.get({
            'filter': {'name': ZabbixActionContainer.action_name_factory(self.dc.name, action_name)}}
        )
        self.assertEqual(len(zabbix_action_), 1, 'action should exist in zabbix')

        if nonexistent_usergroups:
            self.assertRaises(RelatedRemoteObjectDoesNotExist, self.zabbix.action_update, action_name, action_data)
            return

        action_info = self.zabbix.action_update(action_name, action_data)
        zabbix_action_ = self.ezx_zapi.action.get({
            'filter': {'name': ZabbixActionContainer.action_name_factory(self.dc.name, action_name)}}
        )
        self.assertEqual(len(zabbix_action_), 1, 'action should exist in zabbix')
        self.assertEqual(action_info['name'], action_name)

        return action_info

    def _delete_existing_action(self, action_name):
        self.zabbix.action_delete(action_name)
        self.assertListEqual(self.ezx_zapi.action.get({
            'filter': {'name': ZabbixActionContainer.action_name_factory(self.dc.name, action_name)}}
        ), [], 'action should not exist in zabbix anymore')

    def _delete_new_action(self, action_name):
        self.assertListEqual(self.ezx_zapi.action.get({
            'filter': {'name': ZabbixActionContainer.action_name_factory(self.dc.name, action_name)}}
        ), [], 'action should not exist in zabbix anymore')
        self.assertRaises(RemoteObjectDoesNotExist, self.zabbix.action_delete, action_name)

    # noinspection PyMethodMayBeStatic
    def _initial_action_data(self):
        return {
            'usergroups': [],
            'hostgroups': [],
            'enabled': True,
            'message_subject': get_random_string(10),
            'message_text': get_random_string(20),
            'recovery_message_enabled': False,
            'recovery_message_subject': get_random_string(10),
            'recovery_message_text': get_random_string(20),
        }

    def _prepare_action_data(self, action_data, create_usergroups=True):
        if create_usergroups:
            for db_group in action_data.get('usergroups', []):
                self.zabbix.user_group_sync(group=db_group)

        if 'usergroups' in action_data:
            action_data['usergroups'] = [db_group.name for db_group in action_data['usergroups']]

        return action_data

    def _cleanup_action_data(self, action_data):
        for db_group_name in action_data.get('usergroups', []):
            self.zabbix.user_group_delete(db_group_name)

        return action_data

    def test_201_create_get_update_delete_action(self):
        action_name = self.actions[0]
        create_data = dict(
            self._initial_action_data(),
            usergroups=self.db_groups[:2],
            hostgroups=self.hostgroups[:2],
            enabled=False
        )
        self._create_new_action(action_name, create_data, nonexistent_usergroups=True)
        self._prepare_action_data(create_data)
        self.assertDictContainsSubset(create_data, self._create_new_action(action_name, create_data))
        self.assertDictContainsSubset(create_data, self._get_existing_action(action_name))

        update_data = dict(
            usergroups=self.db_groups[2:],
            hostgroups=self.hostgroups[2:],
            enabled=True
        )
        self._update_existing_action(action_name, update_data, nonexistent_usergroups=True)
        self._prepare_action_data(update_data)
        self._create_existing_action(action_name, dict(self._initial_action_data(), **update_data))
        self.assertDictContainsSubset(update_data, self._update_existing_action(action_name, update_data))
        self.assertDictContainsSubset(update_data, self._get_existing_action(action_name))

        self._delete_existing_action(action_name)
        self._cleanup_action_data(create_data)
        self._cleanup_action_data(update_data)

    def test_202_delete_new_action(self):
        action_name = self.actions[0]
        self._delete_new_action(action_name)

    def test_203_get_new_action(self):
        action_name = self.actions[0]
        self._get_new_action(action_name)

    def test_204_update_new_action(self):
        action_name = self.actions[0]
        self._update_new_action(action_name, self._initial_action_data())
