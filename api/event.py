from que.erigonesd import cq


class Event(object):
    """
    Task event dispatched to socket.io monitor.
    """
    _name_ = NotImplemented
    _type_ = 'task-event'

    def __init__(self, task_id, **kwargs):
        self.task_id = task_id
        self.result = kwargs
        self.result['_event_'] = self._name_

    def send(self):
        with cq.events.default_dispatcher() as eventer:
            eventer.send(self._type_, uuid=self.task_id, **self.result)
