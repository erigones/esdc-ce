from .backends.abstract import LOG, MonitoringError
from .backends import get_monitoring, del_monitoring, MonitoringBackend
from frozendict import frozendict


_VM_KWARGS = (
    ('ostype', 1),
    ('ostype_text', 'test'),
    ('dc_name', 'test'),
    ('disk_image', 'test'),
    ('disk_image_abbr', 'test'),
)

VM_KWARGS = frozendict(_VM_KWARGS)
VM_KWARGS_KEYS = tuple(VM_KWARGS.keys())
VM_KWARGS_NIC = frozendict(_VM_KWARGS + (('net', 1), ('nic_id', 2)))
VM_KWARGS_DISK = frozendict(_VM_KWARGS + (('disk', 1), ('disk_id', 2)))