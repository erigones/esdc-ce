from django.db import models
from django.utils.translation import ugettext_lazy as _

# noinspection PyProtectedMember
from vms.mixins import _DcMixin
# noinspection PyProtectedMember
from vms.models.base import _VirtModel, _OSType, _UserTasksModel


class Iso(_VirtModel, _OSType, _DcMixin, _UserTasksModel):
    """
    ISO Image.
    """
    OSTYPE = tuple(i for i in _OSType.OSTYPE if i[0] in _OSType.KVM)

    ACCESS = (
        (_VirtModel.PUBLIC, _('Public')),
        (_VirtModel.PRIVATE, _('Private')),
    )

    OK = 1
    PENDING = 2
    STATUS = (
        (OK, _('ok')),
        (PENDING, _('pending')),
    )

    new = False
    _pk_key = 'iso_id'  # _UserTasksModel

    # Inherited: name, alias, owner, desc, access, created, changed, dc, dc_bound
    status = models.SmallIntegerField(_('Status'), choices=STATUS)
    ostype = models.SmallIntegerField(_('Guest OS type'), choices=OSTYPE, null=True, blank=True)
    # ostype=NULL -> NOT limited to OS Type

    class Meta:
        app_label = 'vms'
        verbose_name = _('ISO image')
        verbose_name_plural = _('ISO images')
        unique_together = (('alias', 'owner'),)

    def __init__(self, *args, **kwargs):
        super(Iso, self).__init__(*args, **kwargs)
        if not self.pk:
            self.new = True

    @property
    def web_data(self):
        return {
            'name': self.name,
            'alias': self.alias,
            'access': self.access,
            'owner': self.owner.username,
            'ostype': self.ostype,
            'desc': self.desc,
            'dc_bound': self.dc_bound_bool,
        }

    def save_status(self, new_status=None, **kwargs):
        """Just update the status field (and other related fields)"""
        if new_status is not None:
            self.status = new_status

        return self.save(update_fields=('status',), **kwargs)
