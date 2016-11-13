from django.db.transaction import atomic
from django.utils.translation import ugettext_lazy as _

from api import serializers as s
from api.validators import validate_alias, validate_dc_bound
from api.accounts.user.utils import ExcludeInternalUsers
from gui.models import User, Role, Permission


class GroupSerializer(s.InstanceSerializer):
    """
    gui.models.role
    """
    _model_ = Role
    _update_fields_ = ('alias', 'permissions', 'users', 'dc_bound')
    _default_fields_ = ('name', 'alias')

    name = s.RegexField(r'^[A-Za-z0-9\._-]*$', max_length=80)
    alias = s.SafeCharField(max_length=80)
    permissions = s.ArrayField(required=False, source='permissions_api')
    users = s.ArrayField(required=False, source='users_api')
    dc_bound = s.BooleanField(source='dc_bound_bool', default=True)
    created = s.DateTimeField(read_only=True, required=False)

    def __init__(self, request, group, *args, **kwargs):
        super(GroupSerializer, self).__init__(request, group, *args, **kwargs)
        if not kwargs.get('many', False):
            self._dc_bound = group.dc_bound

    def _normalize(self, attr, value):
        if attr == 'dc_bound':
            return self._dc_bound
        # noinspection PyProtectedMember
        return super(GroupSerializer, self)._normalize(attr, value)

    # noinspection PyProtectedMember
    @atomic
    def save(self, **kwargs):
        role = self.object
        role.save()

        if role._permissions_to_save is not None:
            role.permissions = role._permissions_to_save

        if role._users_to_save is not None:
            role.user_set = role._users_to_save

    def validate_alias(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            validate_alias(self.object, value)

        return attrs

    def validate_dc_bound(self, attrs, source):
        try:
            value = bool(attrs[source])
        except KeyError:
            pass
        else:
            if value != self.object.dc_bound_bool:
                self._dc_bound = validate_dc_bound(self.request, self.object, value, _('Group'))

        return attrs

    # noinspection PyMethodMayBeStatic
    def validate_permissions(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            permissions = []

            for perm in value:
                try:
                    permission = Permission.objects.get(name=perm)
                except Permission.DoesNotExist:
                    raise s.ObjectDoesNotExist(perm)
                else:
                    permissions.append(permission)

            attrs[source] = permissions
        return attrs

    # noinspection PyMethodMayBeStatic
    def validate_users(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            users = []

            for user in value:
                try:
                    usr = User.objects.filter(ExcludeInternalUsers).select_related('dc_bound').get(username=user)
                except User.DoesNotExist:
                    raise s.ObjectDoesNotExist(user, field_name=_('username'))
                else:
                    users.append(usr)

            attrs[source] = users
        return attrs


class ExtendedGroupSerializer(GroupSerializer):
    dcs = s.DcsField(required=False, source='dc_set')
