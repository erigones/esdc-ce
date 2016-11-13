from logging import getLogger
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.utils import timezone
from django.utils.encoding import force_text
from django.core.cache import cache
from django.core.exceptions import SuspiciousOperation

# noinspection PyProtectedMember
from vms.mixins import _DcBoundMixin
# noinspection PyProtectedMember
from gui.mixins import _AclMixin
from gui.models.permission import (Permission, SuperAdminPermission, AdminPermission, AnyDcPermissionSet,
                                   UserAdminPermission)
from api.permissions import generate_random_security_hash

logger = getLogger(__name__)

CACHE_SUPER_ADMINS_KEY = 'super_admin_ids'
CACHE_DC_ADMINS_KEY = 'admin_ids:dc:%s'  # dc.id required


class User(AbstractBaseUser, PermissionsMixin, _AclMixin, _DcBoundMixin):
    """
    Custom ESDC User class. Sadly, this is a copy of django.contrib.auth.models.AbstractUser with some small changes
    """
    new = False
    _log_name_attr = 'username'  # _UserTasksModel

    username = models.CharField(_('username'), max_length=254, unique=True)
    email = models.EmailField(_('email address'), max_length=254, unique=True)
    first_name = models.CharField(_('first name'), max_length=30)
    last_name = models.CharField(_('last name'), max_length=30)
    is_staff = models.BooleanField(_('SuperAdmin status'), default=False,
                                   help_text=_('Designates whether the user can log into this admin site.'))
    is_active = models.BooleanField(_('active'), default=True,
                                    help_text=_('Designates whether this user should be treated as active. Unselect '
                                                'this instead of deleting accounts.'))
    api_access = models.BooleanField(_('access to API'), default=False, help_text=_('Designates whether the user has '
                                                                                    'access to /api.'))
    api_key = models.CharField(_('API Key'), max_length=254, unique=True, default=generate_random_security_hash)
    callback_key = models.CharField(_('Callback Key'), max_length=254, default=generate_random_security_hash)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    default_dc = models.ForeignKey('vms.Dc', default=settings.VMS_DC_DEFAULT, on_delete=models.SET_DEFAULT, null=True)
    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ('email', 'first_name', 'last_name')

    class Meta:
        app_label = 'gui'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        swappable = 'AUTH_USER_MODEL'

    def __init__(self, *args, **kwargs):
        super(User, self).__init__(*args, **kwargs)
        if not self.pk:
            self.new = True

    def is_authenticated(self):
        return self.is_active

    def get_full_name(self):
        """
        Returns the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """
        Returns the short name for the user.
        """
        return self.first_name

    def email_user(self, *args, **kwargs):
        raise NotImplementedError('sorry')

    def get_profile(self):
        raise NotImplementedError('sorry')

    def get_display_name(self):
        return self.username

    def is_dc_owner(self, dc):
        return dc.owner_id == self.id

    # noinspection PyMethodMayBeStatic
    def is_super_admin(self, request):
        return SuperAdminPermission.name in request.dc_user_permissions

    def is_admin(self, request=None, dc=None):
        if self.is_staff:
            return True

        if self.is_dc_owner(dc or request.dc):
            return True

        return AdminPermission.name in self._get_dc_permissions(request, dc or request.dc)

    def is_user_admin(self, request, dc=None):
        return (self.is_admin(request, dc) and
                UserAdminPermission.name in self._get_dc_permissions(request, dc or request.dc))

    def get_permission_dcs(self, permission_name, admin_required=False):
        """Return QuerySet of DCs where user has a specific permission"""
        from vms.models import Dc

        if self.is_staff:
            return Dc.objects.all()

        qs = Dc.objects.distinct().filter(roles__in=self.roles.filter(permissions__name=permission_name))

        if admin_required:  # User must be admin in DC, beside the specific permission
            qs = qs.filter(Q(owner=self) | Q(roles__in=self.roles.filter(permissions__name=AdminPermission.name)))

        return qs

    def get_dc_permissions(self, dc):
        """Return set of this user's permissions in DC (dc parameter)"""
        if dc.is_dummy:
            return frozenset()

        if self.is_staff:
            perms = {SuperAdminPermission.name, AdminPermission.name}
            perms.update(AnyDcPermissionSet)
            return perms

        if self.is_dc_owner(dc):
            perms = {AdminPermission.name}
        else:
            perms = set()

        # Intersect user.roles and dc.roles and return set of permission names (Django will do only one DB call)
        user_dc_roles = self.roles.filter(pk__in=dc.roles.all())
        perms.update(Permission.objects.distinct().filter(role__in=user_dc_roles).values_list('name', flat=True))

        return perms

    def _get_dc_permissions(self, request=None, dc=None):
        """Decide whether request permissions are in request object, or we need to fetch permissions for another dc"""
        if not request or (dc and request.dc != dc) or request.dc.is_dummy:
            return self.get_dc_permissions(dc)
        return request.dc_user_permissions

    def dcs(self):
        # Use with prefetch_related('roles__dc_set') on user querysets!
        return sorted(set(dc.name for group in self.roles.all() for dc in group.dc_set.all()))

    @staticmethod
    def has_permission(request, permission_name):
        return permission_name in request.dc_user_permissions

    @staticmethod
    def has_permissions(request, permission_names):
        return request.dc_user_permissions.issuperset(permission_names)

    @staticmethod
    def has_any_dc_perm(request):
        return request.dc_user_permissions.intersection(AnyDcPermissionSet)

    @property
    def phone(self):
        return self.userprofile.phone

    @property
    def current_dc(self):
        if not self.default_dc:
            self.default_dc_id = settings.VMS_DC_DEFAULT
            self.save(update_fields=('default_dc',))
        return self.default_dc

    @current_dc.setter
    def current_dc(self, dc):
        if self.default_dc != dc:
            logger.debug('Default DC for user "%s" changed to "%s"', self.username, dc.name)
            self.default_dc = dc
            self.save(update_fields=('default_dc',))

    @property
    def current_dc_id(self):
        if not self.default_dc_id:
            self.default_dc_id = settings.VMS_DC_DEFAULT
            self.save(update_fields=('default_dc',))
        return self.default_dc_id

    @property
    def vms_tags(self):
        return cache.get('user_vms_tags:' + str(self.id), '')

    @vms_tags.setter
    def vms_tags(self, value):
        cache.set('user_vms_tags:' + str(self.id), value)

    @classmethod
    def get_super_admin_ids(cls, timeout=600):
        """Return set of staff users IDs from DB or cache"""
        staff = cache.get(CACHE_SUPER_ADMINS_KEY)

        if staff is None:
            staff = set(cls.objects.filter(is_staff=True).values_list('id', flat=True))
            logger.info('Loading SuperAdmin IDs into cache: %s', staff)
            cache.set(CACHE_SUPER_ADMINS_KEY, staff, timeout=timeout)

        return staff

    @staticmethod
    def clear_super_admin_ids():
        """Clear cached super admin IDs. Do this after changing is_staff attribute on a user."""
        logger.info('Clearing SuperAdmin IDs from cache.')
        return cache.delete(CACHE_SUPER_ADMINS_KEY)

    @classmethod
    def get_dc_admin_ids(cls, dc=None, dc_id=None, timeout=600):
        """Return set of DC admin users IDs from DB or cache"""
        assert dc or dc_id

        if dc:
            dc_id = dc.id

        key = CACHE_DC_ADMINS_KEY % dc_id
        admins = cache.get(key)

        if admins is None:
            if not dc:
                from vms.models import Dc
                dc = Dc.objects.get_by_id(dc_id)

            # Select DC roles which have the admin permission
            admin_dc_roles = dc.roles.filter(permissions__id=AdminPermission.id)
            admins = set(cls.objects.filter(roles__in=admin_dc_roles).values_list('id', flat=True))
            # Add DC owner
            admins.add(dc.owner_id)
            logger.info('Loading Admin IDs for DC "%s" into cache: %s', dc.name, admins)
            cache.set(key, admins, timeout=timeout)

        return admins

    @staticmethod
    def clear_dc_admin_ids(dc=None, dc_id=None):
        """Clear cached DC admin IDs. Do this after changing user groups, group permissions or DC groups."""
        assert dc or dc_id

        if not dc:
            from vms.models import Dc
            dc = Dc.objects.get_by_id(dc_id)

        logger.info('Clearing Admin IDs for DC "%s" from cache.', dc.name)
        return cache.delete(CACHE_DC_ADMINS_KEY % dc.id)

    # noinspection PyUnusedLocal
    @staticmethod
    def post_save(sender, instance, created, **kwargs):
        """Create userprofile after new user is created"""
        if created:
            from gui.models.userprofile import UserProfile
            UserProfile.objects.create(user=instance)

    # noinspection PyUnusedLocal
    @staticmethod
    def pre_save(sender, instance, **kwargs):
        """Some users cannot be updated"""
        if ((instance.id == settings.ADMIN_USER and instance.username != settings.ADMIN_USERNAME) or
                (instance.id == settings.SYSTEM_USER and instance.username != settings.SYSTEM_USERNAME)):
            raise SuspiciousOperation('Username of internal user cannot be modified!')

    # noinspection PyUnusedLocal
    @staticmethod
    def pre_delete(sender, instance, **kwargs):
        """Some users cannot be deleted"""
        if instance.id in (settings.ADMIN_USER, settings.SYSTEM_USER):
            raise SuspiciousOperation('Internal user cannot be deleted!')

    @property
    def alias(self):
        return self.get_full_name()

    @property
    def name(self):
        return self.username

    @property
    def log_alias(self):
        return self.get_full_name()

    @property
    def log_name(self):
        return self.username

    @property
    def log_list(self):
        return self.log_name, self.log_alias, self.pk, self.__class__

    @classmethod
    def get_log_name_lookup_kwargs(cls, log_name_value):
        """Return lookup_key=value DB pairs which can be used for retrieving objects by log_name value"""
        return {cls._log_name_attr: log_name_value}

    @property
    def domain_set(self):
        """Imitates a reverse relationship to Domain model"""
        from pdns.models import Domain  # circular imports

        if self.id:
            return Domain.objects.filter(user=self.id)
        else:
            return Domain.objects.none()

    @property
    def web_data(self):
        """Return dict used in html templates"""
        return {
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'dc_bound': self.dc_bound_bool,
            'groups': [i.name for i in self.roles.all()],
            'is_super_admin': self.is_staff,
            'is_active': self.is_active,
            'api_access': self.api_access,
        }

    def get_relations(self):
        """Return list of objects which this user relates to"""
        related_sets = ('dc', 'vm', 'node', 'storage', 'subnet', 'image', 'vmtemplate', 'iso', 'domain')
        rels = {}

        for i in related_sets:
            for obj in getattr(self, i + '_set').all():
                # noinspection PyProtectedMember
                obj_model_name = force_text(obj._meta.verbose_name)
                rels.setdefault(obj_model_name, []).append(str(obj))

        return rels
