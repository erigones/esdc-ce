from que import TT_DUMMY, TG_DC_BOUND, TG_DC_UNBOUND
from que.utils import TASK_USER, task_id_from_string
from api.event import Event
from api.vm.status.events import VmStatusChanged


class NodeStatusChanged(Event):
    """
    Compute node status change affects compute node GUI and all related VMs.
    """
    _name_ = 'node_status_changed'


# noinspection PyUnusedLocal
def node_status_changed_event(task_id, node, **kwargs):
    """node_status_changed signal callback -> connected in api.signals"""
    siosid = getattr(task_id, 'siosid', None)
    task_id = task_id_from_string(TASK_USER, owner_id=node.owner_id, tt=TT_DUMMY, tg=TG_DC_UNBOUND)
    # Emit NodeStatusChanged into socket.io
    NodeStatusChanged(
        task_id,
        node_hostname=node.hostname,
        status=node.status,
        status_display=node.get_status_display(),
        siosid=siosid,
    ).send()

    for vm in node.vm_set.all():
        tid = task_id_from_string(TASK_USER, owner_id=vm.owner_id, dc_id=vm.dc_id, tt=TT_DUMMY, tg=TG_DC_BOUND)
        # Emit VmStatusChanged into socket.io
        VmStatusChanged(tid, vm).send()
