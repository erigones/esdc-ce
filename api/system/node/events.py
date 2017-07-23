from api.system.update.events import BaseUpdateEvent


class NodeUpdateStarted(BaseUpdateEvent):
    """
    Called from the NodeUpdateView.
    """
    _name_ = 'node_update_started'


class NodeUpdateFinished(BaseUpdateEvent):
    """
    Called from the NodeUpdateView.
    """
    _name_ = 'node_update_finished'
