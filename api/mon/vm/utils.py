from api.mon.utils import MonInternalTask


# noinspection PyAbstractClass
class VmMonInternalTask(MonInternalTask):
    """
    Internal zabbix task for Vm objects.
    """
    abstract = True
