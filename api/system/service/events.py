from django.utils.translation import ugettext as _

from api.event import Event


class SystemReloaded(Event):
    """
    Called from the SystemReloadThread, after the whole system was reloaded.
    """
    _name_ = 'system_reloaded'

    def __init__(self, task_id, request=None, **kwargs):
        if request:
            kwargs['siosid'] = getattr(request, 'siosid', None)

        kwargs['message'] = _('The system was reloaded. Please refresh your browser.')
        super(SystemReloaded, self).__init__(task_id, **kwargs)
