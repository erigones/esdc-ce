from api.decorators import api_view, request_data_defaultdc, setting_required
from api.permissions import IsSuperAdmin
from api.mon.node.api_views import NodeSLAView, NodeHistoryView

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


#: node_status:   GET: Node.STATUS_OPERATIONAL
@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
@setting_required('MON_ZABBIX_NODE_SYNC')
def mon_node_history(request, hostname, graph, item_id=None, data=None):
    """
    Get (:http:get:`GET </mon/node/(hostname)/history/(graph)/(item_id)>`) monitoring history
    for requested node and graph name.

    .. http:get:: /mon/node/(hostname)/history/(graph)/(item_id)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |IsSuperAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg graph: **required** - Graph identificator. One of:

        |  *cpu-usage* - Total compute node CPU consumed by the Node.
        |  *cpu-waittime* - Total amount of time spent in CPU run queue by the Node.
        |  *cpu-load* - 1-minute load average.
        |  *mem-usage* - Total compute node physical memory consumed by the Node.
        |  *swap-usage* - Total compute node swap space used.
        |  *net-bandwidth* - The amount of received and sent network traffic through \
the virtual network interface.
        |  *net-packets* - The amount of received and sent packets through the virtual network interface.

        :type graph: string
        :arg item_id: **optional** only used with **net-bandwidth** and **net-packets** graphs to specify ID of the \
item for which graph should be retrieved.
        :type item_id: integer
        :arg data.since: Return only values that have been received after the given UNIX timestamp
(default: now - 1 hour)
        :type data.since: integer
        :arg data.until: Return only values that have been received before the given UNIX timestamp (default: now)
        :type data.until: integer
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found
        :status 412: Invalid graph / Invalid OS type
        :status 417: Node monitoring disabled
        :status 423: Node is not operational

    """
    return NodeHistoryView(request, hostname, graph, item_id, data).get()
