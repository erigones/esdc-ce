from frozendict import frozendict
import re


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
NODE_KWARGS = frozendict()
NODE_KWARGS_KEYS = tuple(NODE_KWARGS.keys())


class FakeDetailLog(object):
    """
    Dummy list-like object used for collecting log lines.
    """
    def add(self, *args):
        pass


LOG = FakeDetailLog()


class MonitoringError(Exception):
    """
    Base monitoring exception. Other monitoring exceptions must inherit from this class.
    """
    pass


class AbstractMonitoringBackend(object):
    """
    Base Monitoring class. Other monitoring backends must inherit from this class.
    """
    NOT_CLASSIFIED = 0
    INFORMATION = 1
    WARNING = 2
    AVERAGE = 3
    HIGH = 4
    DISASTER = 5
    RE_MONITORING_HOSTGROUPS = re.compile(r'^[\w\s.\-,\"{\}]+$')

    def __init__(self, dc, **kwargs):
        self.dc = dc

    @property
    def connected(self):
        raise NotImplementedError

    def reset_cache(self):
        raise NotImplementedError

    @classmethod
    def vm_send_alert(cls, vm, msg, **kwargs):
        raise NotImplementedError

    @classmethod
    def node_send_alert(cls, node, msg, **kwargs):
        raise NotImplementedError

    def vm_sla(self, vm_node_history):
        raise NotImplementedError

    def vm_history(self, vm_host_id, items, zhistory, since, until, items_search=None):
        raise NotImplementedError

    def is_vm_host_created(self, vm):
        raise NotImplementedError

    def vm_sync(self, vm, force_update=False, task_log=LOG):
        raise NotImplementedError

    def vm_disable(self, vm, task_log=LOG):
        raise NotImplementedError

    def vm_delete(self, vm, internal=True, external=True, task_log=LOG):
        raise NotImplementedError

    def node_sla(self, node_hostname, since, until):
        raise NotImplementedError

    def node_sync(self, node, task_log=LOG):
        raise NotImplementedError

    def node_status_sync(self, node, task_log=LOG):
        raise NotImplementedError

    def node_delete(self, node, task_log=LOG):
        raise NotImplementedError

    def node_history(self, node_id, items, zhistory, since, until, items_search=None):
        raise NotImplementedError

    def template_list(self):
        raise NotImplementedError

    def hostgroup_list(self, prefix=''):
        raise NotImplementedError

    def alert_list(self, prefix=False):
        raise NotImplementedError

    def synchronize_user_group(self, group=None, dc_as_group=None):
        raise NotImplementedError

    def delete_user_group(self, name):
        raise NotImplementedError

    def synchronize_user(self, user):
        raise NotImplementedError

    def delete_user(self, name):
        raise NotImplementedError

    def action_list(self):
        raise NotImplementedError

    def action_update(self, action):
        raise NotImplementedError

    def action_create(self, action):
        raise NotImplementedError

    def action_delete(self, name):
        raise NotImplementedError

    def action_detail(self, name):
        raise NotImplementedError

# TODO rename usergroups, users, actions to pattern (name)_(action)