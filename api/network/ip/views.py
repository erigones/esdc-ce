from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsAnyDcNetworkAdmin, IsSuperAdmin
from api.network.ip.api_views import NetworkIPView, NetworkIPPlanView

__all__ = ('net_ip_list', 'net_ip', 'subnet_ip_list')


@api_view(('GET', 'POST', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcNetworkAdmin,))
def net_ip_list(request, name, data=None):
    """
    List (:http:get:`GET </network/(name)/ip>`) all IP addresses in a network (name).
    Delete (:http:delete:`DELETE </network/(name)/ip>`) list (data.ips) of IP addresses in the network (name).

    .. http:get:: /network/(name)/ip

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
        :arg data.full: Return list of objects with all network IP address details (default: false)
        :type data.full: boolean
        :arg data.usage: Filter by usage (1 - Server [in DB], 2 - Server [on compute node], 3 - Compute node, 9 - Other)
        :type data.usage: integer
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``ip``, ``hostname`` (default: ``id``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Network not found
        :status 412: Invalid usage

    .. http:delete:: /network/(name)/ip

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
        :arg data.ips: **required** List of IPs to be deleted
        :type data.ips: array
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Network not found / IP address not found
        :status 412: Invalid ips / Invalid ips value
        :status 428: IP address is used by VM / IP address is used by Compute node
    """
    return NetworkIPView(request, name, None, data, many=True).response()


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcNetworkAdmin,))
def net_ip(request, name, ip, data=None):
    """
    Show (:http:get:`GET </network/(name)/ip/(ip)>`), create (:http:post:`POST </network/(name)/ip/(ip)>`,
    update (:http:put:`PUT </network/(name)/ip/(ip)>`) or delete (:http:delete:`DELETE </network/(name)/ip/(ip)>`)
    a network IP address.

    .. http:get:: /network/(name)/ip/(ip)

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
        :arg ip: **required** - IP address
        :type ip: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Network not found / IP address not found

    .. http:post:: /network/(name)/ip/(ip)

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
        :arg ip: **required** - IP address
        :type ip: string
        :arg data.usage: Purpose of this IP address. Only server (1) IP addresses can be used for virtual servers \
(1 - Server, 9 - Other) (default: 1)
        :type data.usage: integer
        :arg data.note: Short comment
        :type data.node: string
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Network not found
        :status 406: IP address already exists

    .. http:put:: /network/(name)/ip/(ip)

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
        :arg ip: **required** - IP address
        :type ip: string
        :arg data.usage: Purpose of this IP address. Only server (1) IP addresses can be used for virtual servers \
(1 - Server, 9 - Other)
        :type data.usage: integer
        :arg data.note: Short comment
        :type data.node: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Network not found / IP address not found

    .. http:delete:: /network/(name)/ip/(ip)

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
        :arg ip: **required** - IP address
        :type ip: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Network not found / IP address not found
        :status 428: IP address is used by VM / IP address is used by Compute node

    """
    return NetworkIPView(request, name, ip, data).response()


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def subnet_ip_list(request, subnet=None, data=None):
    """
    List (:http:get:`GET </network/ip/(subnet)>`) all IP addresses in a subnet (optional).

    .. http:get:: /network/ip/(subnet)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg subnet: Show only IP addresses in this subnet. The subnet should be in CIDR notation
        :type subnet: string
        :arg data.full: Return list of objects with all network IP address details (default: false)
        :type data.full: boolean
        :arg data.usage: Filter by usage (1 - Server [in DB], 2 - Server [on compute node], 3 - Compute node, 9 - Other)
        :type data.usage: integer
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``ip``, ``net``, ``hostname`` \
(default: ``ip``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Network not found
        :status 412: Invalid subnet / Invalid usage

    """
    return NetworkIPPlanView(request, subnet, data).get()
