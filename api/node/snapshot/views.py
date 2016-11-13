from api.decorators import api_view, request_data_defaultdc, setting_required
from api.permissions import IsSuperAdmin
from api.utils.db import get_object
from api.node.snapshot.api_views import NodeVmSnapshotList
from vms.models import NodeStorage

__all__ = ('node_vm_snapshot_list',)


@api_view(('GET', 'PUT'))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
@setting_required('VMS_VM_SNAPSHOT_ENABLED', dc_bound=False)
def node_vm_snapshot_list(request, hostname, zpool, data=None):
    """
    List (:http:get:`GET </node/(hostname)/storage/(zpool)/snapshot>`) all VM snapshots on compute node storage or
    synchronize (:http:put:`PUT </node/(hostname)/storage/(zpool)/snapshot>`) snapshots of all VM's disks
    on a compute node storage with snapshots saved in database.

    .. http:get:: /node/(hostname)/storage/(zpool)/snapshot

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg data.full: Return list of objects with all snapshot details (default: false)
        :type data.full: boolean
        :arg data.disk_id: Filter by disk number/ID
        :type data.disk_id: integer
        :arg data.type: Filter by snapshot type (1 - Automatic, 2 - Manual)
        :type data.type: integer
        :arg data.vm: Filter by server hostname
        :type data.vm: string
        :arg data.define: Filter by snapshot definition name
        :type data.define: string
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``disk_id``, ``hostname``, \
``size``, ``created`` (default: ``-created``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Storage not found
        :status 412: Invalid disk_id / Invalid snapshot type

    .. http:put:: /node/(hostname)/storage/(zpool)/snapshot

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Storage not found
        :status 423: Node is not operational

    """
    ns = get_object(request, NodeStorage, {'node__hostname': hostname, 'zpool': zpool},
                    exists_ok=True, noexists_fail=True, sr=('node', 'storage'))

    return NodeVmSnapshotList(request, ns, data).response()
