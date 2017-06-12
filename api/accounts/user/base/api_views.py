from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.db.models import Q
from django.db import connection

from api.api_views import APIView
from api.fields import get_boolean_value
from api.status import HTTP_201_CREATED, HTTP_200_OK
from api.exceptions import PermissionDenied
from api.accounts.user.base.serializers import ApiKeysSerializer, UserSerializer, ExtendedUserSerializer
from api.accounts.user.utils import get_user, get_users
from api.accounts.messages import LOG_USER_CREATE, LOG_USER_UPDATE, LOG_USER_DELETE
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from gui.models import User, AdminPermission
from vms.models import Dc, DefaultDc
from api.mon.alerting.tasks import mon_user_changed


class UserView(APIView):
    serializer = UserSerializer
    dc_bound = False
    order_by_default = order_by_fields = ('username',)
    order_by_field_map = {'created': 'id'}

    def __init__(self, request, username, data, many=False):
        super(UserView, self).__init__(request)
        self.username = username
        self.data = data
        self.many = many
        sr = ('dc_bound', 'default_dc')
        pr = ()

        if not settings.ACL_ENABLED and self.data:
            self.data.pop('groups', None)

        if self.extended:
            self.serializer = ExtendedUserSerializer
            pr = ('roles__dc_set',)

        if username:
            self.user = get_user(request, username, sr=sr, pr=pr, data=data)
        else:
            if self.full or self.extended:
                if self.extended:
                    pr = ('roles', 'roles__dc_set')
                else:
                    pr = ('roles',)
            else:
                sr = ()
                pr = ()

            self.user = get_users(request, data=data, sr=sr, pr=pr, where=Q(is_active=self.active),
                                  order_by=self.order_by)

    def is_active(self, data):
        return self.request.method == 'GET' and get_boolean_value(data.get('active', True))

    @property
    def active(self):
        if self.data:
            return self.is_active(self.data)
        else:
            return True

    def user_modify(self, update=False, serializer=None):
        affected_groups = ()

        if not serializer:
            serializer = self.serializer

        user = self.user
        ser = serializer(self.request, user, data=self.data, partial=update)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=user, dc_bound=False)

        ser.save()
        if update:
            msg = LOG_USER_UPDATE
            status = HTTP_200_OK
        else:
            msg = LOG_USER_CREATE
            status = HTTP_201_CREATED

        res = SuccessTaskResponse(self.request, ser.data, status=status, obj=user, msg=msg, owner=ser.object,
                                  detail_dict=ser.detail_dict(), dc_bound=False)

        if serializer == UserSerializer:
            # User's is_staff attribute was changed -> Clear the cached list of super admins
            if ser.is_staff_changed:
                User.clear_super_admin_ids()

            # User's groups were changed, which may affect the cached list of DC admins for DCs which are attached
            # to these groups. So we need to clear the list of admins cached for each affected DC
            # noinspection PyProtectedMember
            if user._roles_to_save is not None:
                # noinspection PyProtectedMember
                affected_groups = set(user._roles_to_save)
                affected_groups.update(ser.old_roles)
                affected_dcs = Dc.objects.distinct().filter(roles__in=affected_groups,
                                                            roles__permissions__id=AdminPermission.id)
                for dc in affected_dcs:
                    User.clear_dc_admin_ids(dc)

            # User was removed from some groups and may loose access to DCs which are attached to this group
            # So we better set his current_dc to default_dc
            if ser.old_roles:
                user.current_dc = DefaultDc()

        connection.on_commit(lambda: mon_user_changed.call(self.request, user_name=ser.object.username,
                                                           affected_groups=tuple(
                                                               group.id for group in affected_groups)))
        return res

    def get(self):
        return self._get(self.user, self.data, self.many, field_name='username')

    def post(self):
        if not self.request.user.is_staff and self.data:
            self.data.pop('dc_bound', None)  # default DC binding cannot be changed when creating object

        return self.user_modify(update=False)

    def put(self):
        return self.user_modify(update=True)

    def delete(self):
        user = self.user
        # Predefined users can not be deleted
        if user.id in (settings.ADMIN_USER, settings.SYSTEM_USER, self.request.user.id):
            raise PermissionDenied

        relations = user.get_relations()
        if relations:
            message = {
                'detail': _('Cannot delete user, because he has relations to some objects.'),
                'relations': relations
            }
            return FailureTaskResponse(self.request, message, obj=user, dc_bound=False)

        dd = {'email': user.email, 'date_joined': user.date_joined}
        was_staff = user.is_staff
        old_roles = list(user.roles.all())
        ser = self.serializer(self.request, user)
        ser.object.delete()
        connection.on_commit(lambda: mon_user_changed.call(self.request, user_name=ser.object.username,
                                                           affected_groups=tuple(group.id for group in old_roles)))
        res = SuccessTaskResponse(self.request, None, obj=user, msg=LOG_USER_DELETE, detail_dict=dd, dc_bound=False)

        # User was removed, which may affect the cached list of DC admins for DCs which are attached to user's groups
        # So we need to clear the list of admins cached for each affected DC
        affected_dcs = Dc.objects.distinct().filter(roles__in=old_roles, roles__permissions__id=AdminPermission.id)
        for dc in affected_dcs:
            User.clear_dc_admin_ids(dc)

        if was_staff:
            User.clear_super_admin_ids()

        return res

    def api_key(self):
        # Allow show and regenerate API keys only for logged in users
        if self.request.auth == 'api_key':
            raise PermissionDenied

        if self.request.method.lower() == 'get':
            return self._get(self.user, self.data, serializer=ApiKeysSerializer)
        else:
            # noinspection PyTypeChecker
            return self.user_modify(update=True, serializer=ApiKeysSerializer)
