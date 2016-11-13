from api.decorators import api_view, request_data, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.exceptions import NodeIsNotOperational, ObjectAlreadyExists
from api.node.utils import get_node
from api.node.vm.api_views import NodeVmView, VmHarvestView
from vms.models import Vm

__all__ = ('node_vm_list', 'harvest_vm')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def node_vm_list(request, hostname, data=None):
    """
    List (:http:get:`GET </node/(hostname)/vm>`) VMs existing on a specific compute node (hostname).

    .. http:get:: /node/(hostname)/vm

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg data.full: Return list of objects with some VM details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended VM details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``hostname`` (default: ``hostname``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    node = get_node(request, hostname)

    return NodeVmView(request, node, data).get(many=True)


@api_view(('POST',))
@request_data(permissions=(IsSuperAdmin,))
def harvest_vm(request, hostname, data=None):
    """
    Fetch server metadata from compute node and create server(s) in the DB
    (:http:post:`POST </node/(hostname)/vm-harvest>`).

    .. http:post:: /node/(hostname)/vm-harvest

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg data.vm: Optional server uuid. Fetch all servers defined on the compute node if not provided
        :type data.vm: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found
        :status 406: VM already exists
        :status 423: Node is not operational
    """
    node = get_node(request, hostname, dc=request.dc, exists_ok=True, noexists_fail=True)
    vm = data.get('vm', None)

    if vm:
        if Vm.objects.filter(uuid=vm).exists():
            raise ObjectAlreadyExists(model=Vm)

    if node.status != node.ONLINE:
        raise NodeIsNotOperational

    return VmHarvestView(request, node, vm_uuid=vm).post()
