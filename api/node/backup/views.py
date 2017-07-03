from api.decorators import api_view, request_data_defaultdc, setting_required
from api.permissions import IsSuperAdmin
from api.node.utils import get_node
from api.vm.backup.vm_backup_list import VmBackupList
from api.vm.backup.utils import output_extended_backup_count
from api.vm.backup.vm_define_backup import BackupDefineView
from vms.models import BackupDefine

__all__ = ('node_vm_define_backup_list', 'node_vm_backup_list')


#: vm_status:   GET:
@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
@setting_required('VMS_VM_BACKUP_ENABLED', dc_bound=False)
def node_vm_define_backup_list(request, hostname, data=None):
    """
    List (:http:get:`GET </node/(hostname)/define/backup>`) all backup definitions targeted onto a specific backup node.

    .. http:get:: /node/(hostname)/define/backup

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |Superadmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg data.full: Return list of objects with all backup definition details (default: false)
        :type data.full: boolean
        :arg data.extended: Include total number of backups for each backup definition (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``disk_id``, ``hostname``, \
``created`` (default: ``hostname,-created``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    node = get_node(request, hostname, exists_ok=True, noexists_fail=True)
    extra = output_extended_backup_count(request, data)
    # TODO: check indexes
    bkp_define = BackupDefine.objects.select_related('vm', 'vm__dc', 'node', 'zpool', 'periodic_task',
                                                     'periodic_task__crontab')\
                                     .filter(node=node).order_by(*BackupDefineView.get_order_by(data))

    if extra:
        bkp_define = bkp_define.extra(extra)

    return BackupDefineView(request, data=data).get(None, bkp_define, many=True, extended=bool(extra))


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
