from logging import getLogger

from django.utils.translation import ugettext as _

from api.event import Event
from que.utils import task_id_from_request

logger = getLogger(__name__)


class VmDefineHostnameChanged(Event):
    """
    Inform users about hostname change.
    """
    _name_ = 'vm_define_hostname_changed'

    def __init__(self, request, vm, old_hostname):
        siosid = getattr(request, 'siosid', None)
        task_id = task_id_from_request(request, owner_id=vm.owner.id)
        msg = _('Hostname of server %(alias)s changed from %(old_hostname)s to %(new_hostname)s. '
                'Please refresh your browser.' % {'alias': vm.alias, 'old_hostname': old_hostname,
                                                  'new_hostname': vm.hostname})

        super(VmDefineHostnameChanged, self).__init__(
            task_id,
            siosid=siosid,
            vm_hostname=old_hostname,
            new_hostname=vm.hostname,
            new_alias=vm.alias,
            message=msg
        )

    def send(self):
        try:
            super(VmDefineHostnameChanged, self).send()
        except Exception as exc:
            logger.error('Error sending vm_define_hostname_changed event')
            logger.exception(exc)
