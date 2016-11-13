from api.decorators import api_view, request_data
from api.permissions import IsAdmin, IsSuperAdminOrReadOnly
from api.dc.node.api_views import DcNodeView

__all__ = ('dc_node_list', 'dc_node')


@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_node_list(request, data=None):
    """
    List (:http:get:`GET </dc/(dc)/node>`) available compute nodes in current datacenter.

    .. http:get:: /dc/(dc)/node

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg data.full: Return list of objects with all node related details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended compute node details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``hostname`` (default: ``hostname``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found
    """
    return DcNodeView(request, None, data).get(many=True)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_node(request, hostname, data=None):
    """
    Show (:http:get:`GET </dc/(dc)/node/(hostname)>`),
    create (:http:post:`POST </dc/(dc)/node/(hostname)>`),
    change (:http:put:`PUT </dc/(dc)/node/(hostname)>`) or
    remove (:http:delete:`DELETE </dc/(dc)/node/(hostname)>`)
    a compute node (hostname) association with a datacenter (dc).

    .. http:get:: /dc/(dc)/node/(hostname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg hostname: **required** - Compute node hostname
        :type hostname: string
        :arg data.extended: Display extended compute node details (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Node not found

    .. http:post:: /dc/(dc)/node/(hostname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg hostname: **required** - Compute node hostname
        :type hostname: string
        :arg data.strategy: Attachment strategy (1 - Shared, 2 - Shared with limit, 3 - Reserved) (default: 1)
        :type data.strategy: integer
        :arg data.cpu: CPU (core) count reservation or limit (not used in `Shared` strategy, otherwise required)
        :type data.cpu: integer
        :arg data.ram: RAM size (MB) reservation or limit (not used in `Shared` strategy, otherwise required)
        :type data.ram: integer
        :arg data.disk: Local disk pool size (MB) reservation or limit \
(not used in `Shared` strategy, otherwise required)
        :type data.disk: integer
        :arg data.priority: Higher priority (0 - 9999) means that the automatic node chooser \
will more likely choose this node  (default: 100)
        :type data.priority: integer
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found / Node not found
        :status 406: Node already exists

    .. http:put:: /dc/(dc)/node/(hostname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg hostname: **required** - Compute node hostname
        :type hostname: string
        :arg data.strategy: Attachment strategy (1 - Shared, 2 - Shared with limit, 3 - Reserved)
        :type data.strategy: integer
        :arg data.cpu: CPU (core) count reservation or limit (not used in `Shared` strategy, otherwise required)
        :type data.cpu: integer
        :arg data.ram: RAM size (MB) reservation or limit (not used in `Shared` strategy, otherwise required)
        :type data.ram: integer
        :arg data.disk: Local disk pool size (MB) reservation or limit \
(not used in `Shared` strategy, otherwise required)
        :type data.disk: integer
        :arg data.priority: Higher priority (0 - 9999) means that the automatic node chooser \
will more likely choose this node
        :type data.priority: integer
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found / Node not found

    .. http:delete:: /dc/(dc)/node/(hostname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg hostname: **required** - Compute node hostname
        :type hostname: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found / Node not found
        :status 428: Node has VMs in datacenter / Node has VM backups in datacenter

    """
    return DcNodeView(request, hostname, data).response()
