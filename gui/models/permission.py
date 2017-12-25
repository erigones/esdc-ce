from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.functional import SimpleLazyObject

__all__ = (
    'SuperAdminPermission',
    'AdminPermission',
    'NetworkAdminPermission',
    'ImageAdminPermission',
    'ImageImportAdminPermission',
    'TemplateAdminPermission',
    'IsoAdminPermission',
    'UserAdminPermission',
    'DnsAdminPermission',
    'MonitoringAdminPermission',
)


class Permission(models.Model):
    """
    Permissions used by Danube Cloud, both GUI and API, this is different than the ones in core Django
    """
    is_dummy = False
    name = models.CharField(_('name'), max_length=80, unique=True)
    alias = models.CharField(_('alias'), max_length=80)

    class Meta:
        app_label = 'gui'
        verbose_name = _('Permission')
        verbose_name_plural = _('Permissions')

    def __unicode__(self):
        return '%s' % self.alias


class SuperAdminPermission(object):
    """
    Dummy special permission for users with is_staff=True.
    """
    is_dummy = True
    id = pk = None
    name = 'super_admin'
    alias = 'SuperAdmin'


AdminPermission = SimpleLazyObject(lambda: Permission.objects.get(name='admin'))
NetworkAdminPermission = SimpleLazyObject(lambda: Permission.objects.get(name='network_admin'))
ImageAdminPermission = SimpleLazyObject(lambda: Permission.objects.get(name='image_admin'))
ImageImportAdminPermission = SimpleLazyObject(lambda: Permission.objects.get(name='image_import_admin'))
TemplateAdminPermission = SimpleLazyObject(lambda: Permission.objects.get(name='template_admin'))
IsoAdminPermission = SimpleLazyObject(lambda: Permission.objects.get(name='iso_admin'))
UserAdminPermission = SimpleLazyObject(lambda: Permission.objects.get(name='user_admin'))
DnsAdminPermission = SimpleLazyObject(lambda: Permission.objects.get(name='dns_admin'))
MonitoringAdminPermission = SimpleLazyObject(lambda: Permission.objects.get(name='monitoring_admin'))

# Set of strange DC-mixed permission names
AnyDcPermissionSet = frozenset([
    'network_admin',
    'image_admin',
    'image_import_admin'
    'template_admin',
    'iso_admin',
    'user_admin',
    'dns_admin',
    'monitoring_admin',
])
