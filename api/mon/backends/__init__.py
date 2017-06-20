from __future__ import absolute_import
from django.conf import settings

from . import zabbix
from . import dummy

BACKEND_ALIASES = {
    'dummy': dummy,
    'zabbix': zabbix
}

DEFAULT_BACKEND = 'zabbix'


def get_monitoring(dc, **kwargs):
    backend = BACKEND_ALIASES[getattr(settings, 'MONITORING_BACKEND', DEFAULT_BACKEND)]
    return backend.get_monitoring(dc, **kwargs)


def del_monitoring(dc):
    backend = BACKEND_ALIASES[getattr(settings, 'MONITORING_BACKEND', DEFAULT_BACKEND)]
    return backend.del_monitoring(dc)


MonitoringBackend = BACKEND_ALIASES[getattr(settings, 'MONITORING_BACKEND', DEFAULT_BACKEND)].MonitoringBackendClass
