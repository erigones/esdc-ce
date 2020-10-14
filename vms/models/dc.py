from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.db import models
from django.core.cache import cache

# noinspection PyProtectedMember
from gui.mixins import _AclMixin
from vms.utils import DefAttrDict
# noinspection PyProtectedMember
from vms.models.base import _VirtModel, _JsonPickleModel, _UserTasksModel
# noinspection PyProtectedMember
from vms.models.cache import _CacheModel, CacheManager


class Dc(_AclMixin, _VirtModel, _JsonPickleModel, _CacheModel, _UserTasksModel):
    """
    Datacenter.
    """
    VMS_SIZE_TOTAL_DC_KEY = 'vms-size-total-dc:%s'  # %s = dc.id

    ACCESS = (
        (_VirtModel.PUBLIC, _('Public')),
        (_VirtModel.PRIVATE, _('Private')),
    )

    # Inherited: id, name, alias, owner, desc, access, created, changed, json
    site = models.CharField(_('Site hostname'), max_length=260, unique=True)

    _pk_key = 'dc_id'  # _UserTasksModel
    # _CacheModel
    cache_fields = ('id', 'name', 'site')
    objects = CacheManager(cache_fields)
    is_dummy = False

    class Meta:
        app_label = 'vms'
        verbose_name = _('Datacenter')
        verbose_name_plural = _('Datacenters')
        unique_together = (('alias', 'owner'),)

    def is_default(self):
        return self.id == settings.VMS_DC_DEFAULT

    @property
    def web_data(self):
        """Return dict used in html templates"""
        return {
            'name': self.name,
            'alias': self.alias,
            'access': self.access,
            'owner': self.owner.username,
            'groups': [i.name for i in self.roles.all()],  # Not using values_list, because roles.all() is prefetched
            'desc': self.desc,
            'site': self.site,
        }

    def save_setting(self, key, value, save=True):
        """Set item in json['settings'] object"""
        return self.save_item(key, value, save=save, metadata='settings')

    def delete_setting(self, key, save=True):
        """Delete item from json['settings'] object"""
        return self.delete_item(key, save=save, metadata='settings')

    @property
    def custom_settings(self):
        """Custom (overridden) datacenter settings stored in json"""
        return self.json.get('settings', {})

    @custom_settings.setter
    def custom_settings(self, value):
        """Custom (overridden) datacenter settings stored in json"""
        self.save_item('settings', value, save=False)

    @property
    def settings(self):
        """Return a settings dictionary with defaults pointing to settings.py"""
        return DefAttrDict(self.custom_settings, defaults=settings)

    @property
    def domain(self):  # Needed in vm.available_domains
        return self.settings.VMS_VM_DOMAIN_DEFAULT

    @domain.setter
    def domain(self, value):
        self.save_setting('VMS_VM_DOMAIN_DEFAULT', str(value), save=False)

    def get_user_permissions(self, user):
        """Return set of user permissions in this DC"""
        if not user.is_authenticated():
            return frozenset()
        return user.get_dc_permissions(self)

    @property
    def size_vms(self):
        return cache.get(self.VMS_SIZE_TOTAL_DC_KEY % self.pk) or 0

    @property
    def size_snapshots(self):
        from vms.models.snapshot import Snapshot
        return Snapshot.get_total_dc_size(self)

    @property
    def size_backups(self):
        from vms.models.backup import Backup
        return Backup.get_total_dc_size(self)

    @property
    def domain_dc_bound_set(self):
        """Return queryset of DC-bound domains"""
        from pdns.models import Domain

        return Domain.objects.filter(dc_bound=self.id)

    def get_bound_objects(self):
        """Return list of objects which this datacenter relates to"""
        related_sets = ('subnet', 'image', 'vmtemplate', 'iso', 'user', 'role', 'domain')
        rels = {}

        for cls in related_sets:
            rels[cls] = list(getattr(self, cls + '_dc_bound_set').all())

        return rels


# noinspection PyPep8Naming
def DummyDc():
    """
    Dummy/Anonymous Datacenter for anonymous users.
    """
    dc = Dc.objects.get_by_id(settings.VMS_DC_DEFAULT)
    dc.is_dummy = True
    return dc


DummyDc.id = settings.VMS_DC_DEFAULT


# noinspection PyPep8Naming
def DefaultDc():
    """
    Return default Datacenter from cache.
    """
    return Dc.objects.get_by_id(settings.VMS_DC_DEFAULT)


DefaultDc.id = settings.VMS_DC_DEFAULT


class DomainDc(models.Model):
    """
    M2N table for DCs and Domains, because both models are in separate databases.
    This relationship should be in pdns.models.Domain, but the public DNS project does not need it.
    """
    dc = models.ForeignKey(Dc, on_delete=models.CASCADE)
    domain_id = models.IntegerField(db_index=True)

    class Meta:
        app_label = 'vms'
        db_table = 'vms_domain_dc'
        unique_together = (('dc', 'domain_id'),)

    # noinspection PyUnusedLocal
    @classmethod
    def domain_post_delete(cls, sender, instance, **kwargs):
        """Delete DomainDc related entries when a Domain is deleted"""
        cls.objects.filter(domain_id=instance.id).delete()
