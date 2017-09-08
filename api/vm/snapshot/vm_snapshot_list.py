from vms.models import Snapshot
from que import TT_EXEC, TT_AUTO
from que.tasks import execute
from api.api_views import APIView
from api.exceptions import VmIsNotOperational, ExpectationFailed, PreconditionRequired
from api.task.response import SuccessTaskResponse, TaskResponse, FailureTaskResponse
from api.vm.utils import get_vm
from api.vm.messages import LOG_SNAPS_DELETE, LOG_SNAPS_SYNC
from api.vm.snapshot.serializers import SnapshotSerializer
from api.vm.snapshot.utils import (get_disk_id, get_snapshots, filter_disk_id, filter_snap_type, filter_snap_define,
                                   snap_meta)


class VmSnapshotList(APIView):
    """
    api.vm.snapshot.views.vm_snapshot_list
    """
    order_by_default = ('-id',)
    order_by_fields = ('name', 'disk_id', 'size')
    order_by_field_map = {'created': 'id', 'hostname': 'vm__hostname'}
    LOCK = 'vm_snapshot vm:%s disk:%s'

    def __init__(self, request, hostname_or_uuid, data):
        super(VmSnapshotList, self).__init__(request)
        self.data = data
        self.vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True)

    def _check_vm_status(self):
        request, vm = self.request, self.vm

        if not (request.user.is_admin(request) or vm.is_installed()):
            raise PreconditionRequired('VM is not installed')

        if vm.status not in (vm.RUNNING, vm.STOPPED, vm.STOPPING):
            raise VmIsNotOperational

    def get(self):
        request, data, vm = self.request, self.data, self.vm

        # Prepare filter dict
        snap_filter = {'vm': vm}
        filter_disk_id(vm, snap_filter, data)
        filter_snap_type(snap_filter, data)
        filter_snap_define(snap_filter, data)

        # TODO: check indexes
        snapqs = Snapshot.objects.select_related('vm', 'define').filter(**snap_filter).order_by(*self.order_by)

        if self.full or self.extended:
            if snapqs:
                res = SnapshotSerializer(request, snapqs, many=True).data
            else:
                res = []
        else:
            res = list(snapqs.values_list('name', flat=True))

        return SuccessTaskResponse(request, res, vm=vm)

    def delete(self):
        """Delete multiple snapshots"""
        request, data, vm = self.request, self.data, self.vm

        disk_id, real_disk_id, zfs_filesystem = get_disk_id(request, vm, data)
        # Parse data['snapnames']
        snaps, __ = get_snapshots(request, vm, real_disk_id, data)

        self._check_vm_status()

        snaps_lost = snaps.filter(status=Snapshot.LOST)
        msg = LOG_SNAPS_DELETE

        if snaps_lost:
            _result = {'message': 'Snapshots successfully deleted from DB'}
            _detail = "snapnames='%s', disk_id=%s" % (','.join(i.name for i in snaps_lost), disk_id)
            snaps_lost.delete()
            res = SuccessTaskResponse(request, _result, msg=msg, vm=vm, detail=_detail)
            snaps = snaps.filter(status=Snapshot.OK)  # Work with OK snapshots from now on

            if not snaps:
                return res

        elif any(i.status != Snapshot.OK for i in snaps):
            raise ExpectationFailed('VM snapshot status is not OK')

        # Task type (a = automatic, e = manual)
        if getattr(request, 'define_id', None):
            tt = TT_AUTO
        else:
            tt = TT_EXEC

        snapnames = [i.name for i in snaps]
        _apiview_ = {'view': 'vm_snapshot_list', 'method': request.method,
                     'hostname': vm.hostname, 'disk_id': disk_id, 'snapnames': snapnames}
        _detail_ = "snapnames='%s', disk_id=%s" % (','.join(snapnames), disk_id)

        snap_ids = [snap.id for snap in snaps]
        zfs_names = ','.join([snap.zfs_name for snap in snaps])
        lock = self.LOCK % (vm.uuid, real_disk_id)
        cmd = 'esnapshot destroy "%s@%s" 2>&1' % (zfs_filesystem, zfs_names)
        callback = ('api.vm.snapshot.tasks.vm_snapshot_list_cb', {'vm_uuid': vm.uuid, 'snap_ids': snap_ids})

        tid, err = execute(request, vm.owner.id, cmd, meta=snap_meta(vm, msg, _apiview_, _detail_), lock=lock,
                           callback=callback, queue=vm.node.fast_queue, tt=tt)
        if err:
            return FailureTaskResponse(request, err, vm=vm)
        else:
            snaps.update(status=Snapshot.PENDING)
            return TaskResponse(request, tid, msg=msg, vm=vm, api_view=_apiview_, detail=_detail_, data=self.data)

    def put(self):
        """Sync snapshots in DB with snapshots on compute node and update snapshot status and size."""
        request, vm = self.request, self.vm
        disk_id, real_disk_id, zfs_filesystem = get_disk_id(request, vm, self.data)

        self._check_vm_status()

        # Prepare task data
        apiview = {
            'view': 'vm_snapshot_list',
            'method': request.method,
            'hostname': vm.hostname,
            'disk_id': disk_id,
        }
        meta = {
            'output': {'returncode': 'returncode', 'stdout': 'data', 'stderr': 'message'},
            'replace_text': ((vm.uuid, vm.hostname),),
            'msg': LOG_SNAPS_SYNC,
            'vm_uuid': vm.uuid,
            'apiview': apiview,
        }
        detail = 'disk_id=%s' % disk_id
        cmd = 'esnapshot list "%s"' % zfs_filesystem
        lock = self.LOCK % (vm.uuid, real_disk_id)
        callback = ('api.vm.snapshot.tasks.vm_snapshot_sync_cb', {'vm_uuid': vm.uuid, 'disk_id': real_disk_id})

        # Run task
        tid, err = execute(request, vm.owner.id, cmd, meta=meta, lock=lock, callback=callback,
                           queue=vm.node.fast_queue)

        if err:
            return FailureTaskResponse(request, err, vm=vm)
        else:
            return TaskResponse(request, tid, msg=LOG_SNAPS_SYNC, vm=vm, api_view=apiview, detail=detail,
                                data=self.data)
