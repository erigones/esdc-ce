from django.db.transaction import atomic
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from api import serializers as s
from api.email import sendmail
from api.fields import get_boolean_value
from api.permissions import generate_random_security_hash
from api.dc.utils import get_dc
from gui.models import User, Role
from vms.models import Dc

INVALID_USERNAMES = frozenset(['profile'])


class ApiKeysSerializer(s.InstanceSerializer):
    """
    gui.models.User
    """
    _model_ = User
    _update_fields_ = ('api_key', 'callback_key')
    _default_fields_ = ()

    api_key = s.SafeCharField(max_length=254, required=False)
    callback_key = s.SafeCharField(max_length=254, required=False)

    # noinspection PyMethodMayBeStatic
    def validate_api_key(self, attrs, source):
        if get_boolean_value(attrs.pop(source, None)):
            attrs[source] = generate_random_security_hash()

        return attrs

    # noinspection PyMethodMayBeStatic
    def validate_callback_key(self, attrs, source):
        if get_boolean_value(attrs.pop(source, None)):
            attrs[source] = generate_random_security_hash()

        return attrs


class UserSerializer(ApiKeysSerializer):
    """
    gui.models.User
    """
    _model_ = User
    _update_fields_ = ('email', 'first_name', 'last_name', 'is_super_admin', 'is_active', 'api_access', 'api_key',
                       'callback_key', 'groups', 'dc_bound', 'password')
    _default_fields_ = ('username', 'is_super_admin', 'is_active', 'api_access', 'password')

    username = s.RegexField(r'^[A-Za-z0-9@.+_-]*$', max_length=254)
    email = s.EmailField(max_length=254)
    first_name = s.SafeCharField(max_length=30)
    last_name = s.SafeCharField(max_length=30)
    is_super_admin = s.BooleanField(source='is_staff')
    is_active = s.BooleanField()
    api_access = s.BooleanField()
    groups = s.ArrayField(required=False, source='roles_api')
    dc_bound = s.BooleanField(source='dc_bound_bool', default=True)
    created = s.DateTimeField(source='date_joined', read_only=True)
    password = s.CharField()
    old_email = None  # variable for value storage on email change
    is_staff_changed = False
    old_roles = ()

    def __init__(self, request, user, *args, **kwargs):
        super(UserSerializer, self).__init__(request, user, *args, **kwargs)
        if not kwargs.get('many', False):
            self._dc_bound = user.dc_bound

    def _normalize(self, attr, value):
        if attr == 'dc_bound':
            return self._dc_bound
        # noinspection PyProtectedMember
        return super(UserSerializer, self)._normalize(attr, value)

    # noinspection PyProtectedMember
    @atomic
    def save(self, **kwargs):
        user = self.object
        new_flag = (not user.pk or getattr(user, 'new', False))
        user.save()

        if user._roles_to_save is not None:
            self.old_roles = set(user.roles.all())
            user.roles = user._roles_to_save

        # Newly created user via API is automatically marked as verified
        # Creator has to provide correct email, or in user profile set email as not verified (since email is required)!

        # Email change by user will trigger email with verification code so he can finish profile!
        # If admin doesnt set phone user is force to set it and when phone is changed sms verification is send
        if new_flag:
            user.userprofile.email_verified = True
            user.userprofile.phone_verified = True
            user.userprofile.save()

        # Changing a user email makes the email not verified
        # (unless request.user is not part of the staff or registration is disabled)
        if self.old_email and not self.request.user.is_staff and settings.REGISTRATION_ENABLED:
            user.userprofile.email_verified = False
            user.userprofile.email_token = user.userprofile.generate_token(6)
            user.userprofile.save()

            sendmail(
                user,
                'accounts/user/base/profile_verify_subject.txt',
                'accounts/user/base/profile_verify_email.txt', extra_context={
                    'email_token': user.userprofile.email_token,
                }
            )

    def validate_username(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object.id == settings.ADMIN_USER:
                raise s.NoPermissionToModify
            elif value in INVALID_USERNAMES:
                raise s.ValidationError(s.WritableField.default_error_messages['invalid'])

        return attrs

    def validate_email(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            qs = User.objects

            if self.object.pk:
                if self.object.email == value:
                    return attrs
                else:
                    self.old_email = self.object.email
                    qs = qs.exclude(pk=self.object.pk)

            # Check if someone does not use this email (or username) already
            if qs.filter(Q(email__iexact=value) | Q(username__iexact=value)).exists():
                raise s.ValidationError(_('This email is already in use. Please supply a different email.'))

        return attrs

    # noinspection PyMethodMayBeStatic
    def validate_groups(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            groups = []

            for grp in value:
                try:
                    group = Role.objects.get(name=grp)
                except Role.DoesNotExist:
                    raise s.ObjectDoesNotExist(grp)
                else:
                    if self.request.user.is_staff:
                        groups.append(group)
                    else:
                        if group.dc_bound and self._dc_bound and group.dc_bound == self._dc_bound:
                            groups.append(group)
                        else:
                            raise s.ValidationError(_('You don\'t have permission to use DC-unbound groups.'))

            attrs[source] = groups

        return attrs

    def validate_dc_bound(self, attrs, source):
        try:
            value = bool(attrs[source])
        except KeyError:
            pass
        else:
            if value != self.object.dc_bound_bool:
                if not self.request.user.is_staff:
                    raise s.NoPermissionToModify

                if value:
                    data = self.init_data or {}
                    self._dc_bound = get_dc(self.request, data.get('dc', self.request.dc.name))
                else:
                    self._dc_bound = None

        return attrs

    def validate_is_super_admin(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object.is_staff != value:
                if self.object.id == settings.ADMIN_USER:
                    raise s.NoPermissionToModify

                if self.request.user.is_staff:
                    self.is_staff_changed = self.object.is_staff != value
                else:
                    raise s.NoPermissionToModify

        return attrs

    def validate_is_active(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object.is_active != value and self.object.id == settings.ADMIN_USER:
                raise s.NoPermissionToModify

        return attrs

    def validate_api_access(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object.api_access != value and self.object.id == settings.ADMIN_USER:
                raise s.NoPermissionToModify

        return attrs

    def validate(self, attrs):
        # User is or will be bound to this DC
        dc = self._dc_bound

        if attrs.get('dc_bound_bool', self.object.dc_bound_bool) and attrs.get('is_staff', self.object.is_staff):
            self._errors['dc_bound'] = _('A SuperAdmin user cannot be DC-bound.')

        if dc:
            # User is or will be member of these groups
            try:
                groups = attrs['roles_api']
            except KeyError:
                if self.object.pk:
                    groups = self.object.roles.all()
                else:
                    groups = ()

            # A DC-bound user cannot be a member of a group that is assigned to another DC other than user.dc_bound
            if Dc.objects.filter(roles__in=groups).exclude(id=dc.id).exists():
                self._errors['dc_bound'] = s.ErrorList([_("User's group(s) are attached into another datacenter(s).")])

        return attrs

    def _setattr(self, instance, source, value):
        """Update user password if parameter was passed from es"""
        if source == 'password':
            self.object.set_password(value)
        else:
            # noinspection PyProtectedMember
            super(UserSerializer, self)._setattr(instance, source, value)

    def detail_dict(self, **kwargs):
        dd = super(UserSerializer, self).detail_dict(**kwargs)
        # Remove sensitive data from detail dict
        if 'password' in dd:
            dd['password'] = '***'
        if 'api_key' in dd:
            dd['api_key'] = '***'
        if 'callback_key' in dd:
            dd['callback_key'] = '***'
        return dd

    def to_native(self, obj):
        """Updated so we don't display password hash"""
        ret = super(UserSerializer, self).to_native(obj)
        if 'password' in ret:
            del ret['password']
        if 'api_key' in ret:
            ret['api_key'] = '***'
        if 'callback_key' in ret:
            ret['callback_key'] = '***'
        return ret


class ExtendedUserSerializer(UserSerializer):
    dcs = s.ArrayField(required=False, source='dcs', read_only=True)
