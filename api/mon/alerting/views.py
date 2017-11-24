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
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes| - List of all monitoring alerts is retrieved from monitoring server
            * |async-no| - List of all monitoring alerts is retrieved from cache
        :arg data.since: Filter by unix timestamp, start date of the alert history
        :type data.since: timestamp
        :arg data.until: Filter by unix timestamp, end date of the alert history
        :type data.until: tmestamp
        :arg data.last: The number of alerts from alert history to be displayed
        :type data.last: integer
        :arg data.display_items: Include list of related Zabbix triggers
        :type data.display_items: boolean
        :arg data.display_notes: Include list of related Zabbix events and comments
        :type data.display_notes: boolean
        :arg data.hosts_or_groups: List of hostnames or host groups to be filtered by
        :type data.hosts_or_groups: array
        :arg data.show_all: Execute as DC unbound (available for SuperAdmin only)
        :type data.show_all: boolean
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
    """
    return MonAlertView(request, data).get()
