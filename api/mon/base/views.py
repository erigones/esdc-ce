from api.decorators import api_view, request_data, setting_required
from api.permissions import IsAdmin
from api.mon.base.api_views import MonTemplateView

__all__ = ('mon_template_list')


#: node_status:   GET: Node.STATUS_AVAILABLE_MONITORING
@api_view(('GET',))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def mon_template_list(request, data=None):
    """
    Get (:http:get:`GET </mon/template>`)

    .. http:get:: /mon/template

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes| - SLA value is retrieved from monitoring server
            * |async-no| - SLA value is cached
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden

    """
    return MonTemplateView(request, data).get()
