from django.utils.text import Truncator
from django.utils.translation import ugettext_lazy as _

# noinspection PyProtectedMember
from vms.models.base import _DummyModel, _UserTasksModel
from vms.models import Dc


class AbstractMonitoringServer(_DummyModel, _UserTasksModel):
    """
    Abstract model for representing a monitoring server in a DC.
    """
    _pk_key = 'mon_server_id'
    uri = NotImplemented
    name = NotImplemented
    address = NotImplemented
    connection_id = NotImplemented

    # noinspection PyPep8Naming
    class Meta:
        # Required for api.exceptions.ObjectNotFound
        verbose_name_raw = _('Monitoring Server')

    # noinspection PyUnusedLocal
    def __init__(self, dc):
        self.dc = dc
        super(AbstractMonitoringServer, self).__init__()

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.name)

    @property
    def id(self):
        return self.dc.id

    @property
    def owner(self):  # Required by _UserTasksModel
        return self.dc.owner

    @property
    def pk(self):  # Required by task_log
        return str(self.id)

    @property
    def log_name(self):  # Required by task_log
        return Truncator(self.uri).chars(32)

    @property
    def log_alias(self):  # Required by task_log
        return self.name

    @classmethod
    def get_content_type(cls):  # Required by task_log
        return None

    @classmethod
    def get_object_type(cls, content_type=None):  # Required by task_log
        return 'monitoringserver'

    @classmethod
    def get_object_by_pk(cls, pk):
        dc = Dc.objects.get_by_id(pk)
        return cls(dc)


MonitoringServerClass = AbstractMonitoringServer
