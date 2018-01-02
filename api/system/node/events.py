from api.event import Event
from que import TT_DUMMY, TG_DC_UNBOUND
from que.utils import DEFAULT_DC, task_id_from_string


class NodeSystemRestarted(Event):
    """
    Called from node_sysinfo_cb after erigonesd:fast is restarted on a compute node.
    """
    _name_ = 'node_system_restarted'

    def __init__(self, node, **kwargs):
        # Create such a task_id that info is send to SuperAdmins and node owner
        task_id = task_id_from_string(node.owner.id, dummy=True, dc_id=DEFAULT_DC, tt=TT_DUMMY, tg=TG_DC_UNBOUND)
        kwargs['node_hostname'] = node.hostname
        super(NodeSystemRestarted, self).__init__(task_id, **kwargs)
