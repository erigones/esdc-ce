from api.mon.backends.abstract import AbstractMonitoringBackend


class DummyMonitoring(AbstractMonitoringBackend):
    pass


def get_monitoring(dc, **kwargs):
    return DummyMonitoring(dc, **kwargs)


def del_monitoring(dc):
    return True


MonitoringBackendClass = DummyMonitoring
