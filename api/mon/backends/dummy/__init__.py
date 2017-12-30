from api.mon.backends.abstract import AbstractMonitoringBackend
from api.mon.backends.abstract.server import AbstractMonitoringServer


# noinspection PyAbstractClass
class DummyMonitoring(AbstractMonitoringBackend):
    pass


class DummyMonitoringServer(AbstractMonitoringServer):
    """
    Dummy model for representing a monitoring server in a DC.
    """
    Meta = AbstractMonitoringServer.Meta


def get_monitoring(dc, **kwargs):
    return DummyMonitoring(dc, **kwargs)


# noinspection PyUnusedLocal
def del_monitoring(dc):
    return True


MonitoringBackendClass = DummyMonitoring
MonitoringServerClass = DummyMonitoringServer
