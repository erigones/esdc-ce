from django.db import models
from django.utils.translation import ugettext_lazy as _


class _AclMixin(models.Model):
    _roles_to_save = None
    roles = models.ManyToManyField('gui.Role', help_text=_('The groups this object belongs to. A object will get all '
                                                           'permissions granted to each of its groups.'),
                                   verbose_name=_('Groups'), blank=True)

    class Meta:
        app_label = 'gui'
        abstract = True

    @property
    def roles_api(self):
        return [i.name for i in self.roles.all()]

    @roles_api.setter
    def roles_api(self, value):
        self._roles_to_save = value
