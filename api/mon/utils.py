from django.conf import settings

from api.task.internal import InternalTask
from vms.utils import AttrDict


class MonitoringGraph(AttrDict):
    """
    Monitoring graph configuration.
    """
    def __init__(self, name, **params):
        dict.__init__(self)
        self['name'] = name
        self['params'] = params


# noinspection PyAbstractClass
class MonInternalTask(InternalTask):
    """
    Internal zabbix tasks.
    """
    abstract = True

    def call(self, *args, **kwargs):
        # Monitoring is completely disabled
        if not settings.MON_ZABBIX_ENABLED:
            return None

        return super(MonInternalTask, self).call(*args, **kwargs)
