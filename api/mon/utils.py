from django.conf import settings

from api.task.internal import InternalTask


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
