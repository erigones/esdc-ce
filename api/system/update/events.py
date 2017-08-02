from api.event import Event


class BaseUpdateEvent(Event):
    """
    Base class for events below.
    """
    def __init__(self, task_id, request=None, **kwargs):
        if request:
            kwargs['siosid'] = getattr(request, 'siosid', None)

        super(BaseUpdateEvent, self).__init__(task_id, **kwargs)


class SystemUpdateStarted(BaseUpdateEvent):
    """
    Called from the UpdateView.
    """
    _name_ = 'system_update_started'


class SystemUpdateFinished(BaseUpdateEvent):
    """
    Called from the UpdateView.
    """
    _name_ = 'system_update_finished'
