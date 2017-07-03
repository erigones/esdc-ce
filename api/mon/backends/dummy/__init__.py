from api.mon.backends.abstract import AbstractMonitoringBackend


# noinspection PyAbstractClass
class DummyMonitoring(AbstractMonitoringBackend):
    pass


def get_monitoring(dc, **kwargs):
    return DummyMonitoring(dc, **kwargs)


# noinspection PyUnusedLocal
def del_monitoring(dc):
    return True


MonitoringBackendClass = DummyMonitoring
