from api.decorators import api_view, request_data_defaultdc, setting_required
from api.permissions import IsSuperAdmin
from api.node.utils import get_node
from api.vm.backup.vm_backup_list import VmBackupList

__all__ = ('node_vm_backup_list',)


#: vm_status:   GET:
@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
@setting_required('VMS_VM_BACKUP_ENABLED', dc_bound=False)
def node_vm_backup_list(request, hostname, data=None):
    """
    List (:http:get:`GET </node/(hostname)/backup>`) all VM backups on a compute node.

    .. http:get:: /node/(hostname)/backup

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg data.full: Return list of objects with all backup details (default: false)
        :type data.full: boolean
        :arg data.disk_id: Filter by original disk number/ID
        :type data.disk_id: integer
        :arg data.vm: Filter by original server hostname
        :type data.vm: string
        :arg data.define: Filter by backup definition
        :type data.define: string
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``disk_id``, ``hostname``, \
``size``, ``time``, ``created`` (default: ``-created``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Node not found
        :status 412: Invalid disk_id
    """
    node = get_node(request, hostname, exists_ok=True, noexists_fail=True)

    return VmBackupList(request, hostname, data, node=node).get()
