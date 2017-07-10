from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.node.utils import get_node, get_nodes
from api.node.define.api_views import NodeDefineView

__all__ = ('node_define_list', 'node_define')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def node_define_list(request, data=None):
    """
    List (:http:get:`GET </node/define>`) all node definitions.

    .. http:get:: /node/define

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with node network and storage definition details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``hostname`` (default: ``hostname``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    nodes = get_nodes(request, sr=('owner',), order_by=NodeDefineView.get_order_by(data))

    return NodeDefineView(request, nodes, data=data).get(many=True)


@api_view(('GET', 'PUT', 'DELETE'))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def node_define(request, hostname, data=None):
    """
    Show (:http:get:`GET </node/(hostname)/define>`),
    update (:http:put:`PUT </node/(hostname)/define>`) or
    delete (:http:delete:`DELETE </node/(hostname)/define>`)
    a node definition.

    .. http:get:: /node/(hostname)/define

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Node not found

    .. http:put:: /node/(hostname)/define

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg data.status: Compute node status (DB only) (1 - maintenance, 2 - online)
        :type data.status: integer
        :arg data.is_compute: Compute capability
        :type data.is_compute: boolean
        :arg data.is_backup: Backup capability
        :type data.is_backup: boolean
        :arg data.note: Custom text information about this compute node
        :type data.note: string
        :arg data.owner: Node owner
        :type data.owner: string
        :arg data.cpu_coef: Coefficient for calculating the total number of virtual CPUs
        :type data.cpu_coef: float
        :arg data.ram_coef: Coefficient for calculating the maximum amount of memory available for virtual machines
        :type data.ram_coef: float
        :arg data.monitoring_hostgroups: Custom compute node monitoring hostgroups
        :type data.monitoring_hostgroups: array
        :arg data.monitoring_templates: Custom compute node monitoring templates
        :type data.monitoring_templates: array
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found
        :status 409: Node has pending tasks / Node has related objects with pending tasks

    .. http:delete:: /node/(hostname)/define

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg data.force: Force delete even when compute node has existing servers and backups. \
Use with caution! (default: false)
        :type data.force: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found
        :status 409: Node has pending tasks / Node has related objects with pending tasks

    """
    node = get_node(request, hostname, sr=('owner',))

    return NodeDefineView(request, node, data=data).response()
