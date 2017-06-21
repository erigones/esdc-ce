from __future__ import absolute_import
from django.conf import settings

from . import zabbix
from . import dummy

BACKEND_ALIASES = {
    'dummy': dummy,
    'zabbix': zabbix,
}

DEFAULT_BACKEND = 'zabbix'

backend = BACKEND_ALIASES[getattr(settings, 'MONITORING_BACKEND', DEFAULT_BACKEND)]

MonitoringBackend = backend.MonitoringBackendClass


def get_monitoring(dc, **kwargs):
    return backend.get_monitoring(dc, **kwargs)


def del_monitoring(dc):
    return backend.del_monitoring(dc)
