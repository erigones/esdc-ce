from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
# noinspection PyProtectedMember
from vms.mixins import _DcBoundMixin
# noinspection PyProtectedMember
from gui.models.permission import Permission


class Role(_DcBoundMixin):
    """
    Groups used by Danube Cloud, both GUI and API, this is different than the ones in core Django
    """
    new = False
    _users_to_save = None
    _permissions_to_save = None
    _dcs_to_save = None
    _log_name_attr = 'name'  # _UserTasksModel

    name = models.CharField(_('name'), max_length=80, unique=True)
    alias = models.CharField(_('alias'), max_length=80)
    permissions = models.ManyToManyField(Permission, verbose_name=_('permissions'), blank=True)
    created = models.DateTimeField(_('Created'), auto_now_add=True, editable=False)
    changed = models.DateTimeField(_('Last changed'), auto_now=True, editable=False)

    class Meta:
        app_label = 'gui'
        verbose_name = _('User Group')
        verbose_name_plural = _('User Groups')

    def __init__(self, *args, **kwargs):
        super(Role, self).__init__(*args, **kwargs)
        if not self.pk:
            self.new = True

    def __str__(self):
        return '%s' % self.alias

    @property
    def log_name(self):
        return self.name

    @property
    def log_alias(self):
        return self.alias

    @property
    def log_list(self):
        return self.log_name, self.log_alias, self.pk, self.__class__

    @classmethod
    def get_content_type(cls):
        return ContentType.objects.get_for_model(cls)

    @classmethod
    def get_object_type(cls, content_type=None):
        if content_type:
            return content_type.model
        return cls.get_content_type().model

    @classmethod
    def get_object_by_pk(cls, pk):
        # noinspection PyUnresolvedReferences
        return cls.objects.get(pk=pk)

    @classmethod
    def get_log_name_lookup_kwargs(cls, log_name_value):
        """Return lookup_key=value DB pairs which can be used for retrieving objects by log_name value"""
        return {cls._log_name_attr: log_name_value}

    @property
    def permissions_api(self):
        return [i.name for i in self.permissions.all()]

    @permissions_api.setter
    def permissions_api(self, value):
        self._permissions_to_save = value

    @property
    def users_api(self):
        return [i.username for i in self.user_set.all()]

    @users_api.setter
    def users_api(self, value):
        self._users_to_save = value

    @property
    def dcs_api(self):
        return [i.name for i in self.dc_set.all()]

    @dcs_api.setter
    def dcs_api(self, value):
        self._dcs_to_save = value

    @property
    def web_data(self):
        """Return dict used in html templates"""
        return {
            'name': self.name,
            'alias': self.alias,
            'dc_bound': self.dc_bound_bool,
            'users': self.users_api,
            'permissions': self.permissions_api,  # Not using values_list, because permissions.all() is prefetched
            'dcs': self.dcs_api,
        }

    def get_related_dcs(self):
        from vms.models import Dc
        return Dc.objects.filter(roles=self)
