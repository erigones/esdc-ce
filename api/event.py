from que import TT_DUMMY, TG_DC_BOUND, TG_DC_UNBOUND
from que.erigonesd import cq
from que.utils import task_id_from_string


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


class DirectEvent(Event):
    """
    Direct task event dispatched to socket.io monitor, which then sends the signal only to one user.
    """
    def __init__(self, user_id, dc_id=None, **kwargs):
        if dc_id:
            tg = TG_DC_BOUND
        else:
            tg = TG_DC_UNBOUND
            dc_id = cq.conf.ERIGONES_DEFAULT_DC  # DefaultDc().id

        task_id = task_id_from_string(user_id, dummy=True, dc_id=dc_id, tt=TT_DUMMY, tg=tg)
        kwargs['direct'] = True
        super(DirectEvent, self).__init__(task_id, **kwargs)
