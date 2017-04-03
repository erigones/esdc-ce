from api.decorators import api_view, request_data
from api.exceptions import BadRequest
from api.permissions import IsAdminOrReadOnly
from api.vm.utils import get_vm, get_vms
from api.vm.define.vm_define import VmDefineView, VmDefineRevertView
from api.vm.define.vm_define_disk import VmDefineDiskView
from api.vm.define.vm_define_nic import VmDefineNicView


__all__ = ('vm_define', 'vm_define_list', 'vm_define_user', 'vm_define_disk', 'vm_define_disk_list',
           'vm_define_nic', 'vm_define_nic_list', 'vm_define_revert')


#: vm_status:   GET:
# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
def vm_define_list(request, data=None):
    """
    List (:http:get:`GET </vm/define>`) VM definitions.

    .. http:get:: /vm/define

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Display full VM definitions (including disk and nic lists) (default: false)
        :type data.full: boolean
        :arg data.active: Display currently active VM definitions on compute node (default: false)
        :type data.active: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``hostname`` (default: ``hostname``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    vms = get_vms(request, sr=('node', 'owner', 'template'), order_by=VmDefineView.get_order_by(data))

    return VmDefineView(request).get(vms.prefetch_related('tags'), None, many=True)


#: vm_status:   GET:
#: vm_status:  POST:
#: vm_status:   PUT: notcreated, running, stopped, stopping
#: vm_status:DELETE: notcreated
@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
def vm_define(request, hostname_or_uuid, data=None):
    """
    Show (:http:get:`GET </vm/(hostname_or_uuid)/define>`),
    create (:http:post:`POST </vm/(hostname_or_uuid)/define>`),
    change (:http:put:`PUT </vm/(hostname_or_uuid)/define>`) or
    delete (:http:delete:`DELETE </vm/(hostname_or_uuid)/define>`)
    a VM definition.

    .. http:get:: /vm/(hostname_or_uuid)/define

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.full: Display full VM definition (including disk and nic lists) (default: false)
        :type data.full: boolean
        :arg data.active: Display currently active VM definition on compute node (default: false)
        :type data.active: boolean
        :arg data.diff: Display differences between active VM definition on compute node and current configuration \
(default: false)
        :type data.diff: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found

    .. http:post:: /vm/(hostname_or_uuid)/define

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname
        :type hostname_or_uuid: string
        :arg data.alias: Short server name (default: ``hostname``)
        :type data.alias: string
        :arg data.template: VM template name (default: null)
        :type data.template: string
        :arg data.ostype: Operating system type (1 - Linux VM, 2 - SunOS VM, 3 - BSD VM, 4 - Windows VM, \
5 - SunOS Zone, 6 - Linux Zone) (default: 1)
        :type data.ostype: integer
        :arg data.vcpus: **required** - Number of virtual CPUs inside VM (1 - 64)
        :type data.vcpus: integer
        :arg data.ram: **required** - Size of RAM inside VM (32 - 524288 MB)
        :type data.ram: integer
        :arg data.owner: User that owns the VM (default: logged in user)
        :type data.owner: string
        :arg data.node: Name of the host system \
(default: null => will be chosen automatically just before the VM is created)
        :type data.node: string
        :arg data.tags: Custom VM tags (default: [])
        :type data.tags: array
        :arg data.monitored: Enable VM synchronization with monitoring system (default: true)
        :type data.monitored: boolean
        :arg data.monitored_internal: Enable VM synchronization with internal monitoring system \
(requires |SuperAdmin| permission) (default: true)
        :type data.monitored: boolean
        :arg data.installed: Mark the server as installed (default: false)
        :type data.installed: boolean
        :arg data.snapshot_limit_manual: Maximum number of manual snapshots for this VM (default: null [unlimited])
        :type data.snapshot_limit_manual: integer
        :arg data.snapshot_size_limit: Maximum size of all snapshots for this VM (default: null [unlimited])
        :type data.snapshot_size_limit: integer
        :arg data.zpool: The zpool used for the VM zone (default: zones)
        :type data.zpool: string
        :arg data.cpu_shares: Number of VM's CPU shares relative to other VMs (requires |SuperAdmin| permission) \
(default: 100)
        :type data.cpu_shares: integer
        :arg data.zfs_io_priority: IO throttle priority relative to other VMs (requires |SuperAdmin| permission) \
(default: 100)
        :type data.zfs_io_priority: integer
        :arg data.cpu_type: **KVM only**; Type of the virtual CPU exposed to the VM. One of qemu64, host \
(default: qemu64; except for Windows ``ostype`` where the default is host)
        :type data.cpu_type: string
        :arg data.vga: **KVM only**; VGA emulation driver. One of std, cirrus, vmware (default: std)
        :type data.vga: string
        :arg data.routes: Key-value object that maps destinations to gateways. \
Items will be set as static routes in the OS (SunOS Zone only, default: {})
        :type data.routes: object
        :arg data.monitoring_hostgroups: Custom VM monitoring hostgroups (default: [])
        :type data.monitoring_hostgroups: array
        :arg data.monitoring_templates: Custom VM monitoring templates (default: [])
        :type data.monitoring_templates: array
        :arg data.mdata: Customer metadata accessible from within the VM (key=value string pairs) (default: {})
        :type data.mdata: object
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 406: VM already exists

    .. http:put:: /vm/(hostname_or_uuid)/define

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.alias: Short server name
        :type data.alias: string
        :arg data.template: VM template name
        :type data.template: string
        :arg data.vcpus: Number of virtual CPUs inside VM (1 - 64)
        :type data.vcpus: integer
        :arg data.ram: Size of RAM inside VM (32 - 524288 MB)
        :type data.ram: integer
        :arg data.owner: User that owns the VM
        :type data.owner: string
        :arg data.node: Name of the host system
        :type data.node: string
        :arg data.tags: Custom VM tags
        :type data.tags: array
        :arg data.monitored: Enable VM synchronization with monitoring system
        :type data.monitored: boolean
        :arg data.monitored_internal: Enable VM synchronization with internal monitoring system \
(requires |SuperAdmin| permission)
        :type data.monitored: boolean
        :arg data.installed: Mark the server as installed
        :type data.installed: boolean
        :arg data.snapshot_limit_manual: Maximum number of manual snapshots for this VM
        :type data.snapshot_limit_manual: integer
        :arg data.snapshot_size_limit: Maximum size of all snapshots for this VM
        :type data.snapshot_size_limit: integer
        :arg data.zpool: The zpool used for the VM zone
        :type data.zpool: string
        :arg data.cpu_shares: Number of VM's CPU shares relative to other VMs (requires |SuperAdmin| permission)
        :type data.cpu_shares: integer
        :arg data.zfs_io_priority: IO throttle priority relative to other VMs (requires |SuperAdmin| permission)
        :type data.zfs_io_priority: integer
        :arg data.cpu_type: **KVM only**; Type of the virtual CPU exposed to the VM. One of qemu64, host
        :type data.cpu_type: string
        :arg data.vga: **KVM only**; VGA emulation driver. One of std, cirrus, vmware
        :type data.vga: string
        :arg data.routes: Key-value object that maps destinations to gateways. \
Items will be set as static routes in the OS (SunOS Zone only)
        :type data.routes: object
        :arg data.monitoring_hostgroups: Custom VM monitoring hostgroups
        :type data.monitoring_hostgroups: array
        :arg data.monitoring_templates: Custom VM monitoring templates
        :type data.monitoring_templates: array
        :arg data.mdata: Customer metadata accessible from within the VM (key=value string pairs)
        :type data.mdata: object
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 423: VM is not operational / VM is locked or has slave VMs

    .. http:delete:: /vm/(hostname_or_uuid)/define

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 423: VM is not operational / VM is not notcreated / VM is locked or has slave VMs
    """
    vm = get_vm(request, hostname_or_uuid, sr=('owner', 'node', 'template'), check_node_status=None,
                noexists_fail=False, exists_ok=False)

    return VmDefineView(request).response(vm, data, hostname_or_uuid=hostname_or_uuid)


@api_view(('PUT',))
@request_data()  # get_vm() = IsVmOwner
def vm_define_user(request, hostname_or_uuid, data=None):
    """
    vm_define alternative used only for updating hostname and alias.
    Used by non-admin VM owners from GUI.
    """
    vm = get_vm(request, hostname_or_uuid, sr=('owner', 'node', 'template'), check_node_status=None,
                exists_ok=True, noexists_fail=True)
    allowed = {'hostname', 'alias', 'installed'}

    for i in data.keys():  # A copy of keys, because dict can change during iteration
        if i not in allowed:
            del data[i]

    return VmDefineView(request).put(vm, data)


#: vm_status:   GET:
# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
def vm_define_disk_list(request, hostname_or_uuid, data=None):
    """
    List (:http:get:`GET </vm/(hostname_or_uuid)/define/disk>`) VM disk definitions.

    .. http:get:: /vm/(hostname_or_uuid)/define/disk

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.active: Display currently active VM disk definitions on compute node (default: false)
        :type data.active: boolean
        :status 201: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found
    """
    vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True, check_node_status=None)

    return VmDefineDiskView(request).get(vm, None, None, many=True)


#: vm_status:   GET:
#: vm_status:  POST: notcreated, running, stopped, stopping
#: vm_status:   PUT: notcreated, running, stopped, stopping
#: vm_status:DELETE: notcreated, running, stopped, stopping
@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
def vm_define_disk(request, hostname_or_uuid, disk_id=None, data=None):
    """
    Show (:http:get:`GET </vm/(hostname_or_uuid)/define/disk/(disk_id)>`),
    create (:http:post:`POST </vm/(hostname_or_uuid)/define/disk/(disk_id)>`),
    change (:http:put:`PUT </vm/(hostname_or_uuid)/define/disk/(disk_id)>`) or
    delete (:http:delete:`DELETE </vm/(hostname_or_uuid)/define/disk/(disk_id)>`)
    a VM disk definition.

    .. http:get:: /vm/(hostname_or_uuid)/define/disk/(disk_id)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg disk_id: **required** - Disk number/ID (1 - 2)
        :type disk_id: integer
        :arg data.active: Display currently active VM disk definition on compute node (default: false)
        :type data.active: boolean
        :arg data.diff: Display differences between active VM definition on compute node and current configuration \
(default: false)
        :type data.diff: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: VM disk out of range

    .. http:post:: /vm/(hostname_or_uuid)/define/disk/(disk_id)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg disk_id: **required** - Disk number/ID (1 - 2)
        :type disk_id: integer
        :arg data.size: **required** (if not specified in image) - Disk size (1 - 268435456 MB)
        :type data.size: integer
        :arg data.image: **required** (if size is not specified) - Disk image name
        :type data.image: string
        :arg data.model: Disk driver. One of virtio, ide, scsi (default: virtio)
        :type data.model: string
        :arg data.block_size: Block size for this disk (default: depends on OS Type)
        :type data.block_size: integer
        :arg data.compression: Disk compression algorithm. One of off, lzjb, gzip, gzip-N, zle, lz4 (default: off)
        :type data.compression: string
        :arg data.zpool: The zpool in which to create the disk (default: ``vm.zpool`` [zones])
        :type data.zpool: string
        :arg data.boot: Whether this disk should be bootable (default: true for first disk, otherwise false)
        :type data.boot: boolean
        :arg data.refreservation: Minimum amount of space in MB reserved for this disk (KVM only, default: ``size``)
        :type data.refreservation: integer
        :arg data.image_tags_inherit: Whether to update VM tags from image tags (default: true)
        :type data.image_tags_inherit: boolean
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: VM disk out of range / VM disk already exists
        :status 423: VM is not operational / VM is locked or has slave VMs

    .. http:put:: /vm/(hostname_or_uuid)/define/disk/(disk_id)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg disk_id: **required** - Disk number/ID (1 - 2)
        :type disk_id: integer
        :arg data.size: Disk size (1 - 268435456 MB)
        :type data.size: integer
        :arg data.model: Disk driver. One of virtio, ide, scsi
        :type data.model: string
        :arg data.block_size: Block size for this disk
        :type data.block_size: integer
        :arg data.compression: Disk compression algorithm. One of off, lzjb, gzip, gzip-N, zle, lz4
        :type data.compression: string
        :arg data.zpool: The zpool in which to create the disk
        :type data.zpool: string
        :arg data.boot: Whether this disk should be bootable
        :type data.boot: boolean
        :arg data.refreservation: Minimum amount of space in MB reserved for this disk (KVM only)
        :type data.refreservation: integer
        :arg data.image_tags_inherit: Whether to update VM tags from image tags (default: true)
        :type data.image_tags_inherit: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: VM disk out of range
        :status 423: VM is not operational / VM is locked or has slave VMs

    .. http:delete:: /vm/(hostname_or_uuid)/define/disk/(disk_id)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg disk_id: **required** - Disk number/ID (1 - 2)
        :type disk_id: integer
        :arg data.image_tags_inherit: Whether to update VM tags from image tags (default: true)
        :type data.image_tags_inherit: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: VM disk out of range
        :status 423: VM is not operational / VM is locked or has slave VMs

    """
    vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True, sr=('node', 'owner', 'template'),
                check_node_status=None)

    try:
        disk_id = int(disk_id) - 1
    except ValueError:
        raise BadRequest

    return VmDefineDiskView(request).response(vm, disk_id, data)


#: vm_status:   GET:
# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
def vm_define_nic_list(request, hostname_or_uuid, data=None):
    """
    List (:http:get:`GET </vm/(hostname_or_uuid)/define/nic>`) VM NIC definitions.

    .. http:get:: /vm/(hostname_or_uuid)/define/nic

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.active: Display currently active VM NIC definitions on compute node (default: false)
        :type data.active: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found
    """
    vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True, check_node_status=None)

    return VmDefineNicView(request).get(vm, None, None, many=True)


#: vm_status:   GET:
#: vm_status:  POST: notcreated, running, stopped, stopping
#: vm_status:   PUT: notcreated, running, stopped, stopping
#: vm_status:DELETE: notcreated, running, stopped, stopping
@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
def vm_define_nic(request, hostname_or_uuid, nic_id=None, data=None):
    """
    Show (:http:get:`GET </vm/(hostname_or_uuid)/define/nic/(nic_id)>`),
    create (:http:post:`POST </vm/(hostname_or_uuid)/define/nic/(nic_id)>`),
    change (:http:put:`PUT </vm/(hostname_or_uuid)/define/nic/(nic_id)>`) or
    delete (:http:delete:`DELETE </vm/(hostname_or_uuid)/define/nic/(nic_id)>`)
    a VM NIC definition.

    .. http:get:: /vm/(hostname_or_uuid)/define/nic/(nic_id)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg nic_id: **required** - NIC number/ID (1 - 6)
        :type nic_id: integer
        :arg data.active: Display currently active VM NIC definition on compute node (default: false)
        :type data.active: boolean
        :arg data.diff: Display differences between active VM definition on compute node and current configuration \
(default: false)
        :type data.diff: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: VM NIC out of range

    .. http:post:: /vm/(hostname_or_uuid)/define/nic/(nic_id)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg nic_id: **required** - NIC number/ID (1 - 6)
        :type nic_id: integer
        :arg data.net: **required** - Name of a virtual network
        :type data.net: string
        :arg data.ip: Virtual NIC IPv4 address. Must be part of net (default: auto select)
        :type data.ip: string
        :arg data.model: Virtual NIC Model. One of virtio, e1000, rtl8139 (default: virtio)
        :type data.model: string
        :arg data.dns: Create a DNS A record for VM's FQDN? (default: true for first NIC, otherwise false)
        :type data.dns: boolean
        :arg data.use_net_dns: Inherit DNS resolvers from network's resolvers setting (default: false)
        :type data.use_net_dns: boolean
        :arg data.mac: Virtual NIC MAC address (default: auto-generated)
        :type data.mac: string
        :arg data.primary: Use this NICs gateway as VM default gateway (default: true for first NIC, otherwise false)
        :type data.primary: boolean
        :arg data.allow_dhcp_spoofing: Allow packets required for DHCP server (requires |SuperAdmin| permission) \
(default: false)
        :type data.allow_dhcp_spoofing: boolean
        :arg data.allow_ip_spoofing: Allow sending and receiving packets for IP addresses other \
than specified in ``ip`` (requires |SuperAdmin| permission) (default: false)
        :type data.allow_ip_spoofing: boolean
        :arg data.allow_mac_spoofing: Allow sending packets with MAC addresses other than specified in ``mac`` \
(requires |SuperAdmin| permission) (default: false)
        :type data.allow_mac_spoofing: boolean
        :arg data.allow_restricted_traffic: Allow sending packets that are not IPv4, IPv6, or ARP \
(requires |SuperAdmin| permission) (default: false)
        :type data.allow_restricted_traffic: boolean
        :arg data.allow_unfiltered_promisc: Allow VM to have multiple MAC addresses. Use with caution! \
(requires |SuperAdmin| permission) (default: false)
        :type data.allow_unfiltered_promisc: boolean
        :arg data.allowed_ips: List of additional IP addresses that can be used by this VM's NIC and also by \
other VMs. Useful for floating/shared IPs (default: [])
        :type data.allowed_ips: array
        :arg data.monitoring: Use this NIC's IP address for external monitoring \
(default: true for first NIC, otherwise false)
        :type data.monitoring: boolean
        :arg data.set_gateway: Whether to set gateway from network (``data.net``) settings (default: true)
        :type data.set_gateway: boolean
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: VM NIC out of range / VM NIC already exists
        :status 423: VM is not operational / VM is locked or has slave VMs

    .. http:put:: /vm/(hostname_or_uuid)/define/nic/(nic_id)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg nic_id: **required** - NIC number/ID (1 - 6)
        :type nic_id: integer
        :arg data.net: Name of a virtual network
        :type data.net: string
        :arg data.ip: Virtual NIC IPv4 address
        :type data.ip: string
        :arg data.model: Virtual NIC Model. One of virtio, e1000, rtl8139
        :type data.model: string
        :arg data.dns: Create a DNS A record for VM's FQDN?
        :type data.dns: boolean
        :arg data.use_net_dns: Inherit DNS resolvers from network's resolvers setting
        :type data.use_net_dns: boolean
        :arg data.mac: Virtual NIC MAC address
        :type data.mac: string
        :arg data.primary: Use this NICs gateway as VM default gateway
        :type data.primary: boolean
        :arg data.allow_dhcp_spoofing: Allow packets required for DHCP server \
(requires |SuperAdmin| permission)
        :type data.allow_dhcp_spoofing: boolean
        :arg data.allow_ip_spoofing: Allow sending and receiving packets for IP addresses other \
than specified in ``ip`` (requires |SuperAdmin| permission)
        :type data.allow_ip_spoofing: boolean
        :arg data.allow_mac_spoofing: Allow sending packets with MAC addresses other than specified in ``mac`` \
(requires |SuperAdmin| permission)
        :type data.allow_mac_spoofing: boolean
        :arg data.allow_restricted_traffic: Allow sending packets that are not IPv4, IPv6, or ARP \
(requires |SuperAdmin| permission)
        :type data.allow_restricted_traffic: boolean
        :arg data.allow_unfiltered_promisc: Allow VM to have multiple MAC addresses. Use with caution! \
(requires |SuperAdmin| permission)
        :type data.allow_unfiltered_promisc: boolean
        :arg data.allowed_ips: List of additional IP addresses that can be used by this VM's NIC and also by \
other VMs. Useful for floating/shared IPs
        :type data.allowed_ips: array
        :arg data.monitoring: Use this NIC's IP address for external monitoring
        :type data.monitoring: boolean
        :arg data.set_gateway: Whether to set gateway from network (``data.net``) settings
        :type data.set_gateway: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: VM NIC out of range
        :status 423: VM is not operational / VM is locked or has slave VMs

    .. http:delete:: /vm/(hostname_or_uuid)/define/nic/(nic_id)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg nic_id: **required** - NIC number/ID (1 - 6)
        :type nic_id: integer
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: VM NIC out of range
        :status 423: VM is not operational / VM is locked or has slave VMs

    """
    vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True, sr=('node', 'owner', 'template'),
                check_node_status=None)

    try:
        nic_id = int(nic_id) - 1
    except ValueError:
        raise BadRequest

    return VmDefineNicView(request).response(vm, nic_id, data)


#: vm_status:   PUT: running, stopped, stopping
@api_view(('PUT',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
def vm_define_revert(request, hostname_or_uuid, data=None):
    """
    Revert (:http:put:`PUT </vm/(hostname_or_uuid)/define/revert>`)
    whole VM definition (including disks and nics) to currently active VM definition on compute node.

    .. http:put:: /vm/(hostname_or_uuid)/define/revert

        .. warning:: The DNS settings for server's hostname and IP addresses won't be reverted.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found
        :status 409: VM has pending tasks
        :status 417: VM definition unchanged
        :status 423: VM is not operational / VM is not created / VM is locked or has slave VMs
    """
    vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True, sr=('node', 'owner', 'template'),
                check_node_status=None)

    return VmDefineRevertView(request).put(vm, data)
