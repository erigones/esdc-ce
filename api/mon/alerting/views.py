from api.decorators import api_view, request_data, setting_required
from api.permissions import IsAdmin
from api.mon.alerting.api_views import MonAlertView

__all__ = ('mon_alert_list',)


@api_view(('GET',))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def mon_alert_list(request, data=None):
    """
    Get (:http:get:`GET </mon/alert>`) current active alerts or filter monitoring alert history by various parameters.

    .. http:get:: /mon/alert

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |Admin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-yes| - List of all monitoring alerts is retrieved from monitoring server
            * |async-no| - List of all monitoring alerts is retrieved from cache

        :arg data.since: Filter by unix timestamp, start date of the alert history (default: null => all active alerts)
        :type data.since: timestamp
        :arg data.until: Filter by unix timestamp, end date of the alert history (requires ``since``) (default: null)
        :type data.until: timestamp
        :arg data.last: Limit the number of current or historical alerts to fetch (default: null)
        :type data.last: integer
        :arg data.show_events: Include list of related Zabbix events and comments (default: true)
        :type data.show_events: boolean
        :arg data.vm_hostnames: List of virtual server hostnames to be filtered by (default: null)
        :type data.vm_hostnames: array
        :arg data.vm_uuids: List of virtual server UUIDs to be filtered by (default: null)
        :type data.vm_uuids: array
        :arg data.node_hostnames: List of compute node hostnames to be filtered by (requires ``dc_bound=false``) \
(default: null)
        :type data.node_hostnames: array
        :arg data.node_uuids: List of compute node UUIDs to be filtered by (requires ``dc_bound=false``) \
(default: null)
        :type data.node_uuids: array
        :arg data.dc_bound: Execute as DC unbound in the main virtual datacenter => \
fetch all alerts from the main monitoring server (requires |SuperAdmin| permission) (default: false)
        :type data.dc_bound: boolean

        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
    """
    return MonAlertView(request, data=data).get()
