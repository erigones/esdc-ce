from vms.models import BackupDefine
from api.decorators import api_view, request_data, setting_required
from api.permissions import IsAdminOrReadOnly
from api.utils.db import get_object
from api.vm.utils import get_vm, get_vms

from api.vm.snapshot.utils import get_disk_id, filter_disk_id
from api.vm.backup.utils import output_extended_backup_count
from api.vm.backup.vm_define_backup import BackupDefineView
from api.vm.backup.vm_backup import VmBackup
from api.vm.backup.vm_backup_list import VmBackupList

__all__ = ('vm_define_backup_list_all', 'vm_define_backup_list', 'vm_define_backup', 'vm_backup_list', 'vm_backup')


#: vm_status:   GET:
@api_view(('GET',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vms() = IsVmOwner
@setting_required('VMS_VM_BACKUP_ENABLED')
def vm_define_backup_list_all(request, data=None):
    """
    List (:http:get:`GET </vm/define/backup>`) all backup definitions for all VMs.

    .. http:get:: /vm/define/backup

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
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
    extra = output_extended_backup_count(request, data)
    # TODO: check indexes
    bkp_define = BackupDefine.objects.select_related('vm', 'node', 'zpool', 'periodic_task', 'periodic_task__crontab')\
                                     .filter(vm__in=get_vms(request)).order_by(*BackupDefineView.get_order_by(data))

    if extra:
        bkp_define = bkp_define.extra(extra)

    return BackupDefineView(request, data=data).get(None, bkp_define, many=True, extended=bool(extra))


#: vm_status:   GET:
@api_view(('GET',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
@setting_required('VMS_VM_BACKUP_ENABLED')
def vm_define_backup_list(request, hostname_or_uuid, data=None):
    """
    List (:http:get:`GET </vm/(hostname_or_uuid)/define/backup>`) all VM backup definitions.

    .. http:get:: /vm/(hostname_or_uuid)/define/backup

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.full: Return list of objects with all backup definition details (default: false)
        :type data.full: boolean
        :arg data.disk_id: Filter by disk number/ID
        :type data.disk_id: integer
        :arg data.extended: Include total number of backups for each backup definition (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``disk_id``, ``created`` \
(default: ``-created``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found
        :status 412: Invalid disk_id
    """
    vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True, sr=('node', 'owner'))

    query_filter = {'vm': vm}
    query_filter = filter_disk_id(vm, query_filter, data)

    extra = output_extended_backup_count(request, data)
    # TODO: check indexes
    bkp_define = BackupDefine.objects.select_related('vm', 'node', 'zpool', 'periodic_task', 'periodic_task__crontab')\
                                     .filter(**query_filter).order_by(*BackupDefineView.get_order_by(data))

    if extra:
        bkp_define = bkp_define.extra(extra)

    return BackupDefineView(request, data=data).get(vm, bkp_define, many=True, extended=bool(extra))


#: vm_status:   GET:
#: vm_status:  POST: running, stopped, stopping
#: vm_status:   PUT: running, stopped, stopping
#: vm_status:DELETE: running, stopped, stopping
@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
@setting_required('VMS_VM_BACKUP_ENABLED')
def vm_define_backup(request, hostname_or_uuid, bkpdef, data=None):
    """
    Show (:http:get:`GET </vm/(hostname_or_uuid)/define/backup/(bkpdef)>`),
    create (:http:post:`POST </vm/(hostname_or_uuid)/define/backup/(bkpdef)>`),
    remove (:http:delete:`DELETE </vm/(hostname_or_uuid)/define/backup/(bkpdef)>`) or
    update (:http:put:`PUT </vm/(hostname_or_uuid)/define/backup/(bkpdef)>`)
    a VM backup definition and schedule.

    .. http:get:: /vm/(hostname_or_uuid)/define/backup/(bkpdef)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg bkpdef: **required** - Backup definition name
        :type bkpdef: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.extended: Include total number of backups (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found / Backup definition not found
        :status 412: Invalid disk_id

    .. http:post:: /vm/(hostname_or_uuid)/define/backup/(bkpdef)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg bkpdef: **required** - Backup definition name (predefined: hourly, daily, weekly, monthly)
        :type bkpdef: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.type: **required** - Backup type (1 - dataset, 2 - file) (default: 1)
        :type: data.type: integer
        :arg data.node: **required** - Name of the backup node
        :type data.node: string
        :arg data.zpool: **required** - The zpool used on the backup node (default: zones)
        :type data.zpool: string
        :arg data.schedule: **required** - Schedule in UTC CRON format (e.g. 30 4 * * 6)
        :type data.schedule: string
        :arg data.retention: **required** - Maximum number of backups to keep
        :type data.retention: integer
        :arg data.active: Enable or disable backup schedule (default: true)
        :type data.active: boolean
        :arg data.compression: Backup file compression algorithm (0 - none, 1 - gzip, 2 - bzip2) (default: 0)
        :type data.compression: integer
        :arg data.bwlimit: Transfer rate limit in bytes (default: null => no limit)
        :type data.bwlimit: integer
        :arg data.desc: Backup definition description
        :type data.desc: string
        :arg data.fsfreeze: Whether to send filesystem freeze command to QEMU agent socket before \
creating backup snapshot (requires QEMU Guest Agent) (default: false)
        :type data.fsfreeze: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: Backup definition already exists
        :status 412: Invalid disk_id
        :status 423: Node is not operational / VM is not operational

    .. http:put:: /vm/(hostname_or_uuid)/define/backup/(bkpdef)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg bkpdef: **required** - Backup definition name
        :type bkpdef: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.schedule: Schedule in UTC CRON format (e.g. 30 4 * * 6)
        :type data.schedule: string
        :arg data.retention: Maximum number of backups to keep
        :type data.retention: integer
        :arg data.active: Enable or disable backup schedule
        :type data.active: boolean
        :arg data.compression: Backup file compression algorithm (0 - none, 1 - gzip, 2 - bzip2)
        :type data.compression: integer
        :arg data.bwlimit: Transfer rate limit in bytes
        :type data.bwlimit: integer
        :arg data.desc: Backup definition description
        :type data.desc: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Backup definition not found
        :status 412: Invalid disk_id
        :status 423: Node is not operational / VM is not operational

    .. http:delete:: /vm/(hostname_or_uuid)/define/backup/(bkpdef)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg bkpdef: **required** - Backup definition name
        :type bkpdef: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Backup definition not found
        :status 412: Invalid disk_id
        :status 423: Node is not operational / VM is not operational

    """
    vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True)

    disk_id, real_disk_id, zfs_filesystem = get_disk_id(request, vm, data)

    extra = output_extended_backup_count(request, data)

    define = get_object(request, BackupDefine, {'name': bkpdef, 'vm': vm, 'disk_id': real_disk_id},
                        sr=('vm', 'node', 'periodic_task', 'periodic_task__crontab'), extra={'select': extra})

    return BackupDefineView(request, data=data).response(vm, define, extended=bool(extra))


#: vm_status:   GET:
@api_view(('GET', 'DELETE'))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
@setting_required('VMS_VM_BACKUP_ENABLED')
def vm_backup_list(request, hostname_or_uuid, data=None):
    """
    List (:http:get:`GET </vm/(hostname_or_uuid)/backup>`) all VM backups.

    .. http:get:: /vm/(hostname_or_uuid)/backup

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Original server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.full: Return list of objects with all backup details (default: false)
        :type data.full: boolean
        :arg data.disk_id: Filter by original disk number/ID
        :type data.disk_id: integer
        :arg data.define: Filter by backup definition
        :type data.define: string
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``disk_id``, \
``size``, ``time``, ``created`` (default: ``-created``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 412: Invalid disk_id
    """
    return VmBackupList(request, hostname_or_uuid, data).response()


#: vm_status:   GET:
#: vm_status:  POST: running, stopped, stopping
#: vm_status:   PUT: stopped
#: vm_status:DELETE: running, stopped, stopping
@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
@setting_required('VMS_VM_BACKUP_ENABLED')
def vm_backup(request, hostname_or_uuid, bkpname, data=None):
    """
    Show (:http:get:`GET </vm/(hostname_or_uuid)/backup/(bkpname)>`),
    create (:http:post:`POST </vm/(hostname_or_uuid)/backup/(bkpdef)>`),
    delete (:http:delete:`DELETE </vm/(hostname_or_uuid)/backup/(bkpname)>`) or
    restore (:http:put:`PUT </vm/(hostname_or_uuid)/backup/(bkpname)>`)
    a backup of VM's disk.

    .. http:get:: /vm/(hostname_or_uuid)/backup/(bkpname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Original server hostname or uuid
        :type hostname_or_uuid: string
        :arg bkpname: **required** - Backup name
        :type bkpname: string
        :arg data.disk_id: **required** - Original disk number/ID (default: 1)
        :type data.disk_id: integer
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Backup not found
        :status 412: Invalid disk_id

    .. http:post:: /vm/(hostname_or_uuid)/backup/(bkpdef)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg bkpname.bkpdef: **required** - Backup definition name
        :type bkpname.bkpdef: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.note: Backup comment
        :type data.note: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: Backup already exists
        :status 412: Invalid disk_id
        :status 417: DC backup size limit reached
        :status 423: Node is not operational / VM is not operational
        :status 428: VM is not installed

    .. http:put:: /vm/(hostname_or_uuid)/backup/(bkpname)

        .. warning:: A backup restore will restore disk data from the backup into target disk; \
All data created after the backup (including all existing snapshots) on target server will be lost!

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes| - Restore backup
            * |async-no| - Update backup note
        :arg hostname_or_uuid: **required** - Original server hostname or uuid
        :type hostname_or_uuid: string
        :arg bkpname: **required** - Backup name
        :type bkpname: string
        :arg data.disk_id: **required** - Original disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.target_hostname_or_uuid: **required** - Target server hostname or uuid
        :type data.target_hostname_or_uuid: string
        :arg data.target_disk_id: - Target disk number/ID (default: ``disk_id``)
        :type data.target_disk_id: integer
        :arg data.force: Force restore and delete existing snapshots and backups (default: true)
        :type data.force: boolean
        :arg data.note: Backup comment (change note instead of restore if specified)
        :type data.note: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Backup not found
        :status 409: VM has pending tasks
        :status 412: Invalid disk_id / Invalid target_disk_id
        :status 417: VM backup status is not OK / VM has snapshots (force=false)
        :status 423: Node is not operational / VM is not operational / VM is not stopped / VM is locked or has slave VMs
        :status 428: VM brand mismatch / Disk size mismatch / Not enough free space on target storage

    .. http:delete:: /vm/(hostname_or_uuid)/backup/(bkpname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Original server hostname or uuid
        :type hostname_or_uuid: string
        :arg bkpname: **required** - Backup name
        :type bkpname: string
        :arg data.disk_id: **required** - Original disk number/ID (default: 1)
        :type data.disk_id: integer
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Backup not found
        :status 412: Invalid disk_id
        :status 417: VM backup status is not OK
        :status 423: Node is not operational / VM is not operational

    """
    return VmBackup(request, hostname_or_uuid, bkpname, data).response()
