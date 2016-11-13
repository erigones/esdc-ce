from vms.models import SnapshotDefine
from api.decorators import api_view, request_data, setting_required
from api.permissions import IsAdminOrReadOnly
from api.utils.db import get_object
from api.vm.utils import get_vm, get_vms
from api.image.base.views import image_snapshot

from api.vm.snapshot.utils import get_disk_id, filter_disk_id, output_extended_snap_count
from api.vm.snapshot.vm_define_snapshot import SnapshotDefineView
from api.vm.snapshot.vm_snapshot import VmSnapshot
from api.vm.snapshot.vm_snapshot_list import VmSnapshotList

__all__ = ('vm_define_snapshot_list_all', 'vm_define_snapshot_list', 'vm_define_snapshot', 'vm_snapshot_list',
           'vm_snapshot', 'image_snapshot')


#: vm_status:   GET:
@api_view(('GET',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vms() = IsVmOwner
@setting_required('VMS_VM_SNAPSHOT_ENABLED')
def vm_define_snapshot_list_all(request, data=None):
    """
    List (:http:get:`GET </vm/define/snapshot>`) all snapshot definitions for all VMs.

    .. http:get:: /vm/define/snapshot

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with all snapshot definition details (default: false)
        :type data.full: boolean
        :arg data.extended: Include total number of snapshots for each snapshot definition (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``disk_id``, ``hostname``, \
``created`` (default: ``hostname,-created``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    extra = output_extended_snap_count(request, data)
    # TODO: check indexes
    snap_define = SnapshotDefine.objects.select_related('vm', 'periodic_task', 'periodic_task__crontab')\
                                        .filter(vm__in=get_vms(request))\
                                        .order_by(*SnapshotDefineView.get_order_by(data))

    if extra:
        snap_define = snap_define.extra(extra)

    return SnapshotDefineView(request, data=data).get(None, snap_define, many=True, extended=bool(extra))


#: vm_status:   GET:
@api_view(('GET',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
@setting_required('VMS_VM_SNAPSHOT_ENABLED')
def vm_define_snapshot_list(request, hostname, data=None):
    """
    List (:http:get:`GET </vm/(hostname)/define/snapshot>`) all VM snapshot definitions.

    .. http:get:: /vm/(hostname)/define/snapshot

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg data.full: Return list of objects with all snapshot definition details (default: false)
        :type data.full: boolean
        :arg data.disk_id: Filter by disk number/ID
        :type data.disk_id: integer
        :arg data.extended: Include total number of snapshots for each snapshot definition (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``disk_id``, ``created`` \
(default: ``-created``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found
        :status 412: Invalid disk_id
    """
    vm = get_vm(request, hostname, exists_ok=True, noexists_fail=True, sr=('node', 'owner'))

    query_filter = {'vm': vm}
    query_filter = filter_disk_id(vm, query_filter, data)

    extra = output_extended_snap_count(request, data)
    # TODO: check indexes
    snap_define = SnapshotDefine.objects.select_related('vm', 'periodic_task', 'periodic_task__crontab')\
                                        .filter(**query_filter).order_by(*SnapshotDefineView.get_order_by(data))

    if extra:
        snap_define = snap_define.extra(extra)

    return SnapshotDefineView(request, data=data).get(vm, snap_define, many=True, extended=bool(extra))


#: vm_status:   GET:
#: vm_status:  POST: running, stopped, stopping
#: vm_status:   PUT: running, stopped, stopping
#: vm_status:DELETE: running, stopped, stopping
@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vm() = IsVmOwner
@setting_required('VMS_VM_SNAPSHOT_ENABLED')
def vm_define_snapshot(request, hostname, snapdef, data=None):
    """
    Show (:http:get:`GET </vm/(hostname)/define/snapshot/(snapdef)>`),
    create (:http:post:`POST </vm/(hostname)/define/snapshot/(snapdef)>`),
    remove (:http:delete:`DELETE </vm/(hostname)/define/snapshot/(snapdef)>`) or
    update (:http:put:`PUT </vm/(hostname)/define/snapshot/(snapdef)>`)
    a VM snapshot definition and schedule.

    .. http:get:: /vm/(hostname)/define/snapshot/(snapdef)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg snapdef: **required** - Snapshot definition name
        :type snapdef: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.extended: Include total number of snapshots (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found / Snapshot definition not found
        :status 412: Invalid disk_id

    .. http:post:: /vm/(hostname)/define/snapshot/(snapdef)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg snapdef: **required** - Snapshot definition name (predefined: hourly, daily, weekly, monthly)
        :type snapdef: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.schedule: **required** - Schedule in UTC CRON format (e.g. 30 4 * * 6)
        :type data.schedule: string
        :arg data.retention: **required** - Maximum number of snapshots to keep
        :type data.retention: integer
        :arg data.active: Enable or disable snapshot schedule (default: true)
        :type data.active: boolean
        :arg data.desc: Snapshot definition description
        :type data.desc: string
        :arg data.fsfreeze: Whether to send filesystem freeze command to QEMU agent socket before \
creating snapshot (requires QEMU Guest Agent) (default: false)
        :type data.fsfreeze: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: Snapshot definition already exists
        :status 412: Invalid disk_id
        :status 423: Node is not operational / VM is not operational

    .. http:put:: /vm/(hostname)/define/snapshot/(snapdef)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg snapdef: **required** - Snapshot definition name
        :type snapdef: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.schedule: Schedule in UTC CRON format (e.g. 30 4 * * 6)
        :type data.schedule: string
        :arg data.retention: Maximum number of snapshots to keep
        :type data.retention: integer
        :arg data.active: Enable or disable snapshot schedule
        :type data.active: boolean
        :arg data.desc: Snapshot definition description
        :type data.desc: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Snapshot definition not found
        :status 412: Invalid disk_id
        :status 423: Node is not operational / VM is not operational

    .. http:delete:: /vm/(hostname)/define/snapshot/(snapdef)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg snapdef: **required** - Snapshot definition name
        :type snapdef: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Snapshot definition not found
        :status 412: Invalid disk_id
        :status 423: Node is not operational / VM is not operational

    """
    vm = get_vm(request, hostname, exists_ok=True, noexists_fail=True)

    disk_id, real_disk_id, zfs_filesystem = get_disk_id(request, vm, data)

    extra = output_extended_snap_count(request, data)

    define = get_object(request, SnapshotDefine, {'name': snapdef, 'vm': vm, 'disk_id': real_disk_id},
                        sr=('vm', 'periodic_task', 'periodic_task__crontab'), extra={'select': extra})

    return SnapshotDefineView(request, data=data).response(vm, define, extended=bool(extra))


#: vm_status:   GET:
#: vm_status:   PUT: running, stopped, stopping
#: vm_status:DELETE: running, stopped, stopping
@api_view(('GET', 'PUT', 'DELETE'))
@request_data()  # get_vm() = IsVmOwner
@setting_required('VMS_VM_SNAPSHOT_ENABLED')
def vm_snapshot_list(request, hostname, data=None):
    """
    List (:http:get:`GET </vm/(hostname)/snapshot>`) all VM snapshots or
    synchronize (:http:put:`PUT </vm/(hostname)/snapshot>`) snapshots of VM's disk on compute node
    with snapshots saved in database.

    .. http:get:: /vm/(hostname)/snapshot

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg data.full: Return list of objects with all snapshot details (default: false)
        :type data.full: boolean
        :arg data.disk_id: Filter by disk number/ID
        :type data.disk_id: integer
        :arg data.type: Filter by snapshot type (1 - Automatic, 2 - Manual)
        :type data.type: integer
        :arg data.define: Filter by snapshot definition name
        :type data.define: string
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``disk_id``, \
``size``, ``created`` (default: ``-created``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found
        :status 412: Invalid disk_id / Invalid snapshot type

    .. http:put:: /vm/(hostname)/snapshot

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 412: Invalid disk_id
        :status 423: Node is not operational / VM is not operational
        :status 428: VM is not installed

    """
    return VmSnapshotList(request, hostname, data).response()


#: vm_status:   GET:
#: vm_status:  POST: running, stopped, stopping
#: vm_status:   PUT: stopped
#: vm_status:DELETE: running, stopped, stopping
@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data()  # get_vm() = IsVmOwner
@setting_required('VMS_VM_SNAPSHOT_ENABLED')
def vm_snapshot(request, hostname, snapname, data=None):
    """
    Show (:http:get:`GET </vm/(hostname)/snapshot/(snapname)>`),
    create (:http:post:`POST </vm/(hostname)/snapshot/(snapname)>`),
    destroy (:http:delete:`DELETE </vm/(hostname)/snapshot/(snapname)>`) or
    rollback (:http:put:`PUT </vm/(hostname)/snapshot/(snapname)>`)
    a snapshot of VM's disk.

    .. http:get:: /vm/(hostname)/snapshot/(snapname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg snapname: **required** - Snapshot name
        :type snapname: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found / Snapshot not found
        :status 412: Invalid disk_id

    .. http:post:: /vm/(hostname)/snapshot/(snapname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg snapname: **required** - Snapshot name
        :type snapname: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.note: Snapshot comment
        :type data.note: string
        :arg data.fsfreeze: Whether to send filesystem freeze command to QEMU agent socket before \
creating snapshot (requires QEMU Guest Agent) (default: false)
        :type data.fsfreeze: boolean
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: Snapshot already exists
        :status 412: Invalid disk_id
        :status 423: Node is not operational / VM is not operational
        :status 417: VM snapshot limit reached / VM snapshot size limit reached / DC snapshot size limit reached
        :status 428: VM is not installed

    .. http:put:: /vm/(hostname)/snapshot/(snapname)

        .. warning:: A snapshot rollback will restore disk data from the snapshot; \
All data created after the snapshot will be lost (including all newer snapshots)!

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes| - Rollback snapshot
            * |async-no| - Update snapshot note
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg snapname: **required** - Snapshot name
        :type snapname: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.force: Force recursive rollback (default: true)
        :type data.force: boolean
        :arg data.note: Snapshot comment (change note instead of rollback if specified)
        :type data.note: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Snapshot not found
        :status 409: VM has pending tasks
        :status 412: Invalid disk_id
        :status 417: VM snapshot status is not OK / VM has more recent snapshots (force=false)
        :status 423: Node is not operational / VM is not operational / VM is not stopped / VM is locked or has slave VMs

    .. http:delete:: /vm/(hostname)/snapshot/(snapname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg snapname: **required** - Snapshot name
        :type snapname: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Snapshot not found
        :status 412: Invalid disk_id
        :status 417: VM snapshot status is not OK
        :status 423: Node is not operational / VM is not operational

    """
    return VmSnapshot(request, hostname, snapname, data).response()
