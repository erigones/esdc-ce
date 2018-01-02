from api.event import BroadcastEvent


class SystemUpdateStarted(BroadcastEvent):
    """
    Called from the system_update task. Emitted to all socket.io sessions.
    """
    _name_ = 'system_update_started'


class SystemUpdateFinished(BroadcastEvent):
    """
    Called from the UpdateView. Emitted to all socket.io sessions.
    """
    _name_ = 'system_update_finished'
