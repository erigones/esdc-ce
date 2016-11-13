from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.node.base.api_views import NodeView

__all__ = ('node_list', 'node_manage')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def node_list(request, data=None):
    """
    List (:http:get:`GET </node>`) all nodes.

    .. http:get:: /node

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with some compute node details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended compute node details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``hostname`` (default: ``hostname``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return NodeView(request, data=data).get(None, many=True)


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def node_manage(request, hostname, data=None):
    """
    Show (:http:get:`GET </node/(hostname)>`) compute node details.

    .. http:get:: /node/(hostname)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.extended: Display extended compute node details (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Node not found
    """
    return NodeView(request, data=data).response(hostname)
