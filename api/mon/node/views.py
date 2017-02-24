from api.decorators import api_view, request_data_defaultdc, setting_required
from api.permissions import IsSuperAdmin
from api.mon.node.api_views import NodeSLAView, NodeHistoryView

__all__ = ('mon_node_sla', 'mon_node_history')


#: node_status:   GET: Node.STATUS_AVAILABLE_MONITORING
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


#: node_status:   GET: Node.STATUS_AVAILABLE_MONITORING
@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
@setting_required('MON_ZABBIX_NODE_SYNC')
def mon_node_history(request, hostname, graph, data=None):
    """
    Get (:http:get:`GET </mon/node/(hostname)/history/(graph)>`) monitoring history
    for requested node and graph name.

    .. http:get:: /mon/node/(hostname)/history/(graph)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Compute node hostname
        :type hostname: string
        :type graph: string
        :arg graph: **required** - Graph identificator. One of:

        |  *cpu-usage* - Total compute node CPU consumed by the Node.
        |  *cpu-waittime* - Total amount of time spent in CPU run queue by the Node.
        |  *cpu-load* - 1-minute load average.
        |  *mem-usage* - Total compute node physical memory consumed by the Node.
        |  *swap-usage* - Total compute node swap space used.
        |  *net-bandwidth* - The amount of received and sent network traffic through \
the virtual network interface. *requires data.nic*
        |  *net-packets* - The amount of received and sent packets through the \
virtual network interface. *requires data.nic*
        |  *storage-throughput* - The amount of read and written data on the zpool.
        |  *storage-io* - The amount of I/O read and write operations performed on the zpool.
        |  *storage-space* - ZFS zpool space usage by type.

        :arg data.since: Return only values that have been received after the given UNIX timestamp \
(default: now - 1 hour)
        :type data.since: integer
        :arg data.until: Return only values that have been received before the given UNIX timestamp (default: now)
        :type data.until: integer
        :arg data.nic: only used with *net-bandwidth* and *net-packets* graphs \
to specify name of the NIC for which graph should be retrieved.
        :type data.nic: string
        :arg data.zpool: only used with *storage-throughput*, *storage-io* and *storage-space* graphs \
to specify ID of the zpool for which graph should be retrieved.
        :type data.zpool: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found
        :status 412: Invalid graph
        :status 417: Node monitoring disabled
        :status 423: Node is not operational

    """
    return NodeHistoryView(request, hostname, graph, data).get()
