from django.utils.translation import ugettext_lazy as _
from django.db import models


class _DcBoundMixin(models.Model):
    """
    Used by _DcMixin and Users to get dc_bound field.
    """
    dc_bound = models.ForeignKey('vms.Dc', related_name='%(class)s_dc_bound_set', null=True, blank=True, default=None,
                                 on_delete=models.SET_NULL)

    class Meta:
        app_label = 'vms'
        abstract = True

    @property
    def dc_bound_bool(self):
        return bool(self.dc_bound)

    @dc_bound_bool.setter
    def dc_bound_bool(self, value):
        # This looks weird, but is used by some serializers
        self.dc_bound = value


class _DcMixin(_DcBoundMixin):
    """
    Used by VirtModels to get M2N relation to DC and dc_bound field.
    """
    dc = models.ManyToManyField('vms.Dc', verbose_name=_('Datacenter'))

    class Meta:
        app_label = 'vms'
        abstract = True
