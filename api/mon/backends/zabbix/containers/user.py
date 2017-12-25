from django.db.models import Q
from frozendict import frozendict

from vms.models import Dc
from que.tasks import get_task_logger
from api.mon.backends.zabbix.exceptions import RemoteObjectDoesNotExist
from api.mon.backends.zabbix.containers.base import ZabbixBaseContainer
from api.mon.backends.zabbix.containers.media import ZabbixMediaContainer

task_logger = get_task_logger(__name__)


class ZabbixUserContainer(ZabbixBaseContainer):
    """
    Container class for the Zabbix User object.
    """
    ZABBIX_ID_ATTR = 'userid'
    MEDIA_ENABLED = 0  # 0 - enabled, 1 - disabled [sic in zabbix docs]
    USER_QUERY_BASE = frozendict({
        'selectUsrgrps': ('usrgrpid', 'name', 'gui_access'),
        'selectMedias': ('mediatypeid', 'sendto'),
    })

    # noinspection PyUnresolvedReferences
    def __init__(self, *args, **kwargs):
        super(ZabbixUserContainer, self).__init__(*args, **kwargs)
        self.user = None  # type: [gui.models.User]
        self.groups = set()  # type: [ZabbixUserGroupContainer]

    @classmethod
    def synchronize(cls, zapi, user):
        """
        We check whether the user object exists in zabbix. If not, we create it. If it does, we update it.
        """
        try:
            existing_zabbix_user = cls.from_zabbix_alias(zapi, user.username)
        except RemoteObjectDoesNotExist:
            existing_zabbix_user = None

        user_to_sync = cls.from_mgmt_data(zapi, user)

        if user_to_sync.groups and not existing_zabbix_user:  # Create
            user_to_sync.create()
            result = cls.CREATED
        elif user_to_sync.groups and existing_zabbix_user:  # Update
            user_to_sync.zabbix_id = existing_zabbix_user.zabbix_id
            user_to_sync.update_all()
            result = cls.UPDATED
        elif not user_to_sync.groups and existing_zabbix_user:  # Delete
            user_to_sync.delete()
            result = cls.DELETED
        elif not user_to_sync.groups and not existing_zabbix_user:  # No-op
            result = cls.NOTHING
        else:
            raise AssertionError('This should never happen')

        return result

    @classmethod
    def from_mgmt_data(cls, zapi, user):
        container = cls(user.username, zapi=zapi)
        container.user = user
        container.prepare_groups()

        return container

    @classmethod
    def from_zabbix_data(cls, zapi, zabbix_object):
        container = cls(zabbix_object['alias'], zapi=zapi, zabbix_object=zabbix_object)
        container._refresh_groups()

        return container

    @classmethod
    def from_zabbix_alias(cls, zapi, alias):
        params = dict(filter={'alias': alias}, **cls.USER_QUERY_BASE)
        response = cls.call_zapi(zapi, 'user.get', params=params)
        zabbix_object = cls.parse_zabbix_get_result(response)

        return cls.from_zabbix_data(zapi, zabbix_object)

    @classmethod
    def from_zabbix_id(cls, zapi, zabbix_id):
        params = dict(userids=zabbix_id, **cls.USER_QUERY_BASE)
        response = cls.call_zapi(zapi, 'user.get', params=params)
        zabbix_object = cls.parse_zabbix_get_result(response)

        return cls.from_zabbix_data(zapi, zabbix_object)

    @classmethod
    def delete_by_id(cls, zapi, zabbix_id):
        response = cls.call_zapi(zapi, 'user.delete', params=[zabbix_id])

        if cls.parse_zabbix_delete_result(response, 'userids'):
            return cls.DELETED
        else:
            return cls.NOTHING

    @classmethod
    def delete_by_name(cls, zapi, name):
        zabbix_id = cls.fetch_zabbix_id(zapi, name)

        if zabbix_id:
            return cls.delete_by_id(zapi, zabbix_id)
        else:
            return cls.NOTHING

    @classmethod
    def fetch_zabbix_id(cls, zapi, username):
        response = cls.call_zapi(zapi, 'user.get', params={'filter': {'alias': username}})

        # FIXME: Raising MultipleRemoteObjectsReturned can cause endless task loop

        try:
            return int(cls.parse_zabbix_get_result(response, 'userid'))
        except RemoteObjectDoesNotExist:
            return None

    def renew_zabbix_id(self):
        self.zabbix_id = self.fetch_zabbix_id(self._zapi, self.name)

    def update_all(self):
        """
        When updating user in zabbix<3.4, two calls have to be done: first for updating user name and groups and
        second to update user media.
        """
        assert self.zabbix_id, 'A user in zabbix should be first created, then updated. %s has no zabbix_id.' % self
        user_update_request_content = self._get_api_request_object_stub()

        self._attach_group_membership(user_update_request_content)
        self._attach_basic_info(user_update_request_content)

        task_logger.debug('Updating user %s with group info and identity: %s', self.zabbix_id,
                          user_update_request_content)
        self._api_response = self._call_zapi('user.update', params=user_update_request_content)

        user_media_update_request_content = {'users': {'userid': self.zabbix_id}}
        self._attach_media_for_update_call(user_media_update_request_content)

        task_logger.debug('Updating user %s with media: %s', self.zabbix_id, user_media_update_request_content)
        self._api_response = self._call_zapi('user.updatemedia', params=user_media_update_request_content)

    def create(self):
        assert not self.zabbix_id, \
            '%s has the zabbix_id already and therefore you should try to update the object, not create it.' % self

        user_object = {}

        self._attach_group_membership(user_object)
        self._attach_media_for_create_call(user_object)
        self._attach_basic_info(user_object)

        user_object['alias'] = self.user.username
        user_object['passwd'] = self.user.__class__.objects.make_random_password(20)  # TODO let the user set it

        task_logger.debug('Creating user: %s', user_object)
        self._api_response = self._call_zapi('user.create', params=user_object)
        self.zabbix_id = int(self.parse_zabbix_create_result(self._api_response, 'userids'))
        self.zabbix_object = user_object

        return self.CREATED

    def delete(self):
        if not self.zabbix_id:
            self.renew_zabbix_id()

        res = self.delete_by_id(self._zapi, self.zabbix_id)
        self.reset()

        return res

    def _prepare_groups(self):
        from api.mon.backends.zabbix.containers.user_group import ZabbixUserGroupContainer

        yielded_owned_dcs = set()
        user_related_dcs = Dc.objects.filter(Q(owner=self.user) | Q(roles__user=self.user))

        for dc_name, group_name, user_id in user_related_dcs.values_list('name', 'roles__name', 'roles__user'):
            if user_id == self.user.id:
                local_group_name = group_name
            elif dc_name not in yielded_owned_dcs:
                local_group_name = ZabbixUserGroupContainer.OWNERS_GROUP
                yielded_owned_dcs.add(dc_name)
            else:
                continue

            qualified_group_name = ZabbixUserGroupContainer.user_group_name_factory(dc_name, local_group_name)

            try:
                yield ZabbixUserGroupContainer.from_zabbix_name(self._zapi, qualified_group_name, resolve_users=False)
            except RemoteObjectDoesNotExist:
                pass  # We don't create/delete user groups when users are created.

    def prepare_groups(self):
        self.groups = set(self._prepare_groups())

    def _refresh_groups(self):
        from api.mon.backends.zabbix.containers.user_group import ZabbixUserGroupContainer

        self.groups = set(ZabbixUserGroupContainer.from_zabbix_data(self._zapi, group)
                          for group in self.zabbix_object.get('usrgrps', []))

    def refresh(self):
        params = dict(userids=self.zabbix_id, **self.USER_QUERY_BASE)
        self._api_response = self._call_zapi('user.get', params=params)
        zabbix_object = self.parse_zabbix_get_result(self._api_response)
        self.init(zabbix_object)
        self._refresh_groups()
        # TODO refresh media etc

    def _attach_group_membership(self, api_request_object):
        zabbix_ids_of_all_user_groups = [group.zabbix_id for group in self.groups]
        assert self.groups and all(zabbix_ids_of_all_user_groups), \
            'To be able to attach groups (%s) to a user(%s), they all have to be in zabbix first.' % (self.groups, self)
        # This cannot be a set because it's serialized to json, which is not supported for sets:
        api_request_object['usrgrps'] = zabbix_ids_of_all_user_groups

    def update_group_membership(self):
        assert self.zabbix_id, 'A user in zabbix should be first created, then updated. %s has no zabbix_id.' % self
        user_object = self._get_api_request_object_stub()
        self._attach_group_membership(user_object)
        task_logger.debug('Updating user: %s', user_object)
        self._api_response = self._call_zapi('user.update', user_object)
        self.parse_zabbix_update_result(self._api_response, 'userids')

    def _prepare_media(self):
        media = []

        for media_type in ZabbixMediaContainer.MEDIA_TYPES:
            user_media_sendto = ZabbixMediaContainer.extract_sendto_from_user(media_type, self.user)

            if user_media_sendto:
                user_media = ZabbixMediaContainer(media_type, user_media_sendto, zapi=self._zapi)

                try:
                    user_media_data = user_media.to_zabbix_data()
                except RemoteObjectDoesNotExist:
                    task_logger.warning('Cannot create user media for user %s because media type "%s" does not exist '
                                        'in zabbix', self.user, media_type)
                else:
                    media.append(user_media_data)

        return media

    def _attach_media_for_create_call(self, api_request_object):
        api_request_object['user_medias'] = self._prepare_media()

    def _attach_media_for_update_call(self, api_request_object):
        api_request_object['medias'] = self._prepare_media()

    def _attach_basic_info(self, api_request_object):
        api_request_object['name'] = self.user.first_name
        api_request_object['surname'] = self.user.last_name
        # user_object['type']= FIXME self.user.is_superadmin but we miss request

    def _get_api_request_object_stub(self):
        return {'userid': self.zabbix_id}
