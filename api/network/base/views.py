from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsAnyDcNetworkAdmin
from api.network.base.api_views import NetworkView

__all__ = ('net_list', 'net_manage')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsAnyDcNetworkAdmin,))
def net_list(request, data=None):
    """
    List (:http:get:`GET </network>`) all networks.

    .. http:get:: /network

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |NetworkAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with all network details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended network details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``created`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return NetworkView(request, None, data).get(many=True)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcNetworkAdmin,))
def net_manage(request, name, data=None):
    """
    Show (:http:get:`GET </network/(name)>`), create (:http:post:`POST </network/(name)>`,
    update (:http:put:`PUT </network/(name)>`) or delete (:http:delete:`DELETE </network/(name)>`)
    a virtual network.

    .. http:get:: /network/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |NetworkAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Network name
        :type name: string
        :arg data.extended: Display extended network details (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Network not found

    .. http:post:: /network/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |NetworkAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Network name
        :type name: string
        :arg data.alias: Short network name (default: ``name``)
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private, 4 - Deleted) (default: 3)
        :type data.access: integer
        :arg data.owner: User that owns the network (default: logged in user)
        :type data.owner: string
        :arg data.desc: Network description
        :type data.desc: string
        :arg data.network: **required** - IPv4 network prefix in quad-dotted format
        :type data.network: string
        :arg data.netmask: **required** - IPv4 subnet mask in quad-dotted format
        :type data.netmask: string
        :arg data.gateway: **required** - IPv4 gateway in quad-dotted format
        :type data.gateway: string
        :arg data.nic_tag: **required** - NIC tag or device name on compute node
        :type data.nic_tag: string
        :arg data.vlan_id: **required** - 802.1Q virtual LAN ID (0 - 4096; 0 = none)
        :type data.vlan_id: integer
        :arg data.vxlan_id: VXLAN ID required for overlay NIC tags (1 - 16777215, default=``null``)
        :type data.vxlan_id: integer
        :arg data.resolvers: List of IPv4 addresses that can be used as resolvers
        :type data.resolvers: array
        :arg data.dns_domain: Existing domain name used for creating A records for VMs
        :type data.dns_domain: string
        :arg data.ptr_domain: Existing in-addr.arpa domain used for creating PTR associations with VMs
        :type data.ptr_domain: string
        :arg data.dhcp_passthrough: When true, IP addresses for this network are managed by an external service \
(default: false)
        :type data.dhcp_passthrough: boolean
        :arg data.dc_bound: Whether the network is bound to a datacenter (requires |SuperAdmin| permission) \
(default: true)
        :type data.dc_bound: boolean
        :arg data.dc: Name of the datacenter the network will be attached to (**required** if DC-bound)
        :type data.dc: string
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found
        :status 406: Network already exists

    .. http:put:: /network/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |NetworkAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Network name
        :type name: string
        :arg data.alias: Short network name
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private, 4 - Deleted)
        :type data.access: integer
        :arg data.owner: User that owns the network
        :type data.owner: string
        :arg data.desc: Network description
        :type data.desc: string
        :arg data.network: IPv4 network prefix in quad-dotted format
        :type data.network: string
        :arg data.netmask: IPv4 subnet mask in quad-dotted format
        :type data.netmask: string
        :arg data.gateway: IPv4 gateway in quad-dotted format
        :type data.gateway: string
        :arg data.nic_tag: NIC tag or device name on compute node
        :type data.nic_tag: string
        :arg data.vlan_id: 802.1Q virtual LAN ID (0 - 4096; 0 = none)
        :type data.vlan_id: integer
        :arg data.vxlan_id: VXLAN ID required for overlay NIC tags (1 - 16777215)
        :type data.vxlan_id: integer
        :arg data.resolvers: List of IPv4 addresses that can be used as resolvers
        :type data.resolvers: array
        :arg data.dns_domain: Existing domain name used for creating A records for VMs
        :type data.dns_domain: string
        :arg data.ptr_domain: Existing in-addr.arpa domain used for creating PTR associations with VMs
        :type data.ptr_domain: string
        :arg data.dhcp_passthrough: When true, IP addresses for this network are managed by an external service
        :type data.dhcp_passthrough: boolean
        :arg data.dc_bound: Whether the network is bound to a datacenter (requires |SuperAdmin| permission)
        :type data.dc_bound: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Network not found

    .. http:delete:: /network/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |NetworkAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Network name
        :type name: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Network not found
        :status 428: Network is used by some VMs

    """
    return NetworkView(request, name, data).response()
