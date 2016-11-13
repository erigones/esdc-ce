from api.decorators import api_view, request_data
from api.permissions import IsAdmin, IsSuperAdminOrReadOnly
from api.dc.network.api_views import DcNetworkView
from api.network.ip.api_views import NetworkIPView

__all__ = ('dc_network_list', 'dc_network', 'dc_network_ip_list')


@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_network_list(request, data=None):
    """
    List (:http:get:`GET </dc/(dc)/network>`) available networks in current datacenter.

    .. http:get:: /dc/(dc)/network

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg data.full: Return list of objects with all network details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found
    """
    return DcNetworkView(request, None, data).get(many=True)


# noinspection PyUnusedLocal
@api_view(('GET', 'POST', 'DELETE'))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_network(request, name, data=None):
    """
    Show (:http:get:`GET </dc/(dc)/network/(name)>`),
    create (:http:post:`POST </dc/(dc)/network/(name)>`) or
    delete (:http:delete:`DELETE </dc/(dc)/network/(name)>`)
    a network (name) association with a datacenter (dc).

    .. http:get:: /dc/(dc)/network/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - Network name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Network not found

    .. http:post:: /dc/(dc)/network/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - Network name
        :type name: string
        :status 201: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Network not found
        :status 406: Network already exists

    .. http:delete:: /dc/(dc)/network/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - Network name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Network not found
        :status 428: Network is used by some VMs

    """
    return DcNetworkView(request, name, data).response()


@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_network_ip_list(request, name, data=None):
    """
    List (:http:get:`GET </dc/(dc)/network/(name)/ip>`)
    IP addresses in a network (name) used by all servers in a datacenter (dc).

    .. http:get:: /dc/(dc)/network/(name)/ip

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - Network name
        :type name: string
        :arg data.full: Return list of objects with all network IP address details (default: false)
        :type data.full: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Network not found
    """
    return NetworkIPView(request, name, None, data, dc=request.dc, many=True).get()
