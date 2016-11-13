from api.decorators import api_view, request_data_defaultdc, setting_required
from api.permissions import IsSuperAdmin
from api.mon.node.api_views import NodeSLAView

__all__ = ('mon_node_sla',)


#: node_status:   GET: Node.STATUS_OPERATIONAL
@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
@setting_required('MON_ZABBIX_NODE_SLA')  # dc1_settings
def mon_node_sla(request, hostname, yyyymm, data=None):
    """
    Get (:http:get:`GET </mon/node/(hostname)/sla/(yyyymm)>`) SLA for
    requested compute node and month.

    .. http:get:: /mon/node/(hostname)/sla/(yyyymm)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-yes| - SLA value is retrieved from monitoring server
            * |async-no| - SLA value is cached
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg yyyymm: **required** - Time period in YYYYMM format
        :type yyyymm: integer
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found
        :status 412: Invalid yyyymm
        :status 417: Monitoring data not available
        :status 423: Node is not operational

    """
    return NodeSLAView(request, hostname, yyyymm, data).get()
