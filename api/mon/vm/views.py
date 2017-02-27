from api.decorators import api_view, request_data, setting_required
from api.permissions import IsAdminOrReadOnly
from api.mon.vm.api_views import VmMonitoringView, VmSLAView, VmHistoryView

__all__ = ('mon_vm_define', 'mon_vm_sla', 'mon_vm_history')


#: vm_status:   GET:
#: vm_status:   PUT: notcreated, running, stopped, stopping
@api_view(('GET', 'PUT'))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
def mon_vm_define(request, hostname_or_uuid, data=None):
    """
    Show (:http:get:`GET </mon/vm/(hostname_or_uuid)/monitoring>`) or
    update (:http:put:`PUT </mon/vm/(hostname_or_uuid)/monitoring>`)
    a VM's monitoring interface definition.

    .. note:: A VM's monitoring interface is automatically created for \
every :py:func:`monitored VM <api.vm.define.views.vm_define>`.

    .. http:get:: /mon/vm/(hostname_or_uuid)/monitoring

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.active: Display currently active VM monitoring definition in the monitoring system (default: false)
        :type data.active: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found

    .. http:put:: /mon/vm/(hostname_or_uuid)/monitoring

        .. note:: Please use :http:put:`/vm/(hostname_or_uuid)` to update the monitoring interface definition of \
an already deployed VM after changing any of the VM's monitoring interface attributes.

        .. note:: By setting the value of ``port``, ``dns``, ``useip`` and/or ``proxy`` parameter(s) to ``null``, the \
parameter(s) will be set to a default value.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.ip: IPv4 address used for monitoring (automatically updated \
by :py:func:`~api.vm.define.views.vm_define_nic`)
        :type data.ip: string
        :arg data.port: Port number used for monitoring (default: 10050)
        :type data.port: integer
        :arg data.dns: Server hostname (FQDN) used for monitoring connections when ``useip`` is false \
or ``ip`` is not set (default: ``hostname``)
        :type data.dns: string
        :arg data.useip: Whether the monitoring connection should be made via the IP address (default: true)
        :type data.useip: boolean
        :arg data.proxy: Name or ID of the monitoring proxy that is used to monitor the host (default: '' => disabled)
        :type data.proxy: string
        :arg data.hostgroups: Custom VM monitoring hostgroups; same as ``monitoring_hostgroups`` in \
:py:func:`~api.vm.define.views.vm_define` (default: [])
        :type data.hostgroups: array
        :arg data.templates: Custom VM monitoring templates; same as ``monitoring_templates`` in \
:py:func:`~api.vm.define.views.vm_define` (default: [])
        :type data.templates: array

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 423: VM is not operational / VM is locked or has slave VMs
    """
    return VmMonitoringView(request, hostname_or_uuid, data).response()


#: vm_status:   GET: Vm.STATUS_OPERATIONAL
# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data()  # get_vm() = IsVmOwner
@setting_required('MON_ZABBIX_ENABLED')
@setting_required('MON_ZABBIX_VM_SLA')
def mon_vm_sla(request, hostname_or_uuid, yyyymm, data=None):
    """
    Get (:http:get:`GET </mon/vm/(hostname_or_uuid)/sla/(yyyymm)>`) SLA for
    requested server and month.

    .. http:get:: /mon/vm/(hostname_or_uuid)/sla/(yyyymm)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes| - SLA value is retrieved from monitoring server
            * |async-no| - SLA value is cached
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg yyyymm: **required** - Time period in YYYYMM format
        :type yyyymm: integer
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 412: Invalid yyyymm
        :status 417: Monitoring data not available
        :status 423: VM is not operational

    """
    return VmSLAView(request, hostname_or_uuid, yyyymm, data).get()


#: vm_status:   GET: Vm.STATUS_OPERATIONAL
@api_view(('GET',))
@request_data()  # get_vm() = IsVmOwner
@setting_required('MON_ZABBIX_ENABLED')
def mon_vm_history(request, hostname_or_uuid, graph, data=None):
    """
    Get (:http:get:`GET </mon/vm/(hostname_or_uuid)/history/(graph)>`) monitoring history
    for requested server and graph name.

    .. http:get:: /mon/vm/(hostname_or_uuid)/history/(graph)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :type graph: string
        :arg graph: **required** - Graph identificator. One of:

        |  *cpu-usage* - Total compute node CPU consumed by the VM.
        |  *cpu-waittime* - Total amount of time spent in CPU run queue by the VM.
        |  *cpu-load* - 1-minute load average.
        |  *mem-usage* - Total compute node physical memory consumed by the VM.
        |  *swap-usage* - Total compute node swap space used by the VM.
        |  *net-bandwidth* - The amount of received and sent network traffic through \
the virtual network interface. *requires data.nic_id*
        |  *net-packets* - The amount of received and sent packets through the virtual \
network interface. *requires data.nic_id*
        |  *disk-throughput* (KVM only) - The amount of written and read data on \
the virtual hard drive. *requires data.disk_id*
        |  *disk-io* (KVM only) - The amount of write and read I/O operations performed on \
the virtual hard drive. *requires data.disk_id*
        |  *fs-throughput* (SunOS Zone only) - The amount of written and read data \
on the virtual hard drive. *requires data.disk_id*
        |  *fs-io* (SunOS Zone only) - The amount of write and read I/O operations performed on \
the virtual hard drive. *requires data.disk_id*
        |  *vm-disk-logical-throughput* - Aggregated disk throughput on the logical layer \
(with acceleration mechanisms included).
        |  *vm-disk-logical-io* - Aggregated amount or read and write I/O operations on the logical layer \
(with acceleration mechanisms included).
        |  *vm-disk-physical-throughput* - Aggregated disk throughput on the physical (disk) layer.
        |  *vm-disk-physical-io* - Aggregated amount of read and write I/O operations on the physical (disk) layer.
        |  *vm-disk-io-operations* - Aggregated amount of disk I/O operations by latency on the logical layer \
(with acceleration mechanisms included).

        :arg data.since: Return only values that have been received after the given timestamp (default: now - 1 hour)
        :type data.since: integer
        :arg data.until: Return only values that have been received before the given timestamp (default: now)
        :type data.until: integer
        :arg data.disk_id: used only with *disk-throughput*, \
*disk-io*, *fs-throughput*, *fs-io* graphs to specify ID of the disk for which graph should be retrieved.
        :type data.disk_id: integer
        :arg data.nic_id: only used with *net-bandwidth*, *net-packets* \
graphs to specify ID of the NIC for which graph should be retrieved.
        :type data.nic_id: integer
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 412: Invalid graph / Invalid OS type
        :status 417: VM monitoring disabled
        :status 423: VM is not operational

    """
    return VmHistoryView(request, hostname_or_uuid, graph, data).get()
