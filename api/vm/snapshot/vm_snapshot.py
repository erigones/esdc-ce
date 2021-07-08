from vms.models import Snapshot
from que import TT_EXEC, TT_AUTO
from que.tasks import execute
from api.api_views import APIView
from api.exceptions import (VmIsNotOperational, NodeIsNotOperational, VmIsLocked, PreconditionRequired,
                            ExpectationFailed, VmHasPendingTasks)
from api.utils.db import get_object
from api.task.response import SuccessTaskResponse, TaskResponse, FailureTaskResponse
from api.vm.utils import get_vm
from api.vm.messages import LOG_SNAP_CREATE, LOG_SNAP_UPDATE, LOG_SNAP_DELETE
from api.vm.snapshot.serializers import SnapshotSerializer, SnapshotRestoreSerializer
from api.vm.snapshot.utils import get_disk_id, snap_meta, snap_callback


class VmSnapshot(APIView):
    """
    api.vm.snapshot.views.vm_snapshot
    """
    LOCK = 'vm_snapshot vm:%s disk:%s'

    def __init__(self, request, hostname_or_uuid, snapname, data):
        super(VmSnapshot, self).__init__(request)
        self.data = data
        self.vm = vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True,
                              check_node_status=('POST', 'DELETE'))  # custom node check inside put()
        self.disk_id, real_disk_id, self.zfs_filesystem = get_disk_id(request, vm, data)
        self.snap = get_object(request, Snapshot, {'name': snapname, 'vm': vm, 'disk_id': real_disk_id}, sr=('define',))

    @property
    def zpool(self):
        return self.zfs_filesystem.split('/')[0]

    def _check_vm_status(self, vm=None):
        request, vm = self.request, vm or self.vm

        if not (request.user.is_admin(request) or vm.is_installed()):
            raise PreconditionRequired('VM is not installed')

        if vm.status not in (vm.RUNNING, vm.STOPPED, vm.STOPPING):
            raise VmIsNotOperational

    def _check_snap_status(self, lost_ok=False):
        assert self.zfs_filesystem == self.snap.zfs_filesystem

        if not (self.snap.status == Snapshot.OK or (lost_ok and self.snap.status == Snapshot.LOST)):
            raise ExpectationFailed('VM snapshot status is not OK')

    def _check_snap_limit(self):
        try:
            limit = int(self.vm.json_active['internal_metadata'][self.limit_key])
        except (TypeError, KeyError, IndexError):
            pass
        else:
            # TODO: check indexes
            total = Snapshot.objects.filter(vm=self.vm, type=self.snaptype).count()
            if total >= limit:
                raise ExpectationFailed('VM snapshot limit reached')

    def _check_snap_size_limit(self):
        """Issue #chili-848"""
        limit = self.vm.snapshot_size_quota_value
        if limit is not None:
            total = Snapshot.get_total_vm_size(self.vm)
            if total >= limit:
                raise ExpectationFailed('VM snapshot size limit reached')

    def _check_snap_dc_size_limit(self):
        """Issue #chili-848"""
        limit = self.vm.dc.settings.VMS_VM_SNAPSHOT_DC_SIZE_LIMIT

        if limit is not None:
            limit = int(limit)
            total = Snapshot.get_total_dc_size(self.vm.dc)

            if total >= limit:
                raise ExpectationFailed('DC snapshot size limit reached')

    def _get_apiview_detail(self):
        apiview = {'view': 'vm_snapshot', 'method': self.request.method,
                   'hostname': self.vm.hostname, 'disk_id': self.disk_id, 'snapname': self.snap.name}
        detail = "snapname='%s', disk_id=%s" % (self.snap.name, self.disk_id)

        self.snap_define_id = getattr(self.request, 'define_id', None)

        if self.snap_define_id:
            self.tt = TT_AUTO
            self.snaptype = Snapshot.AUTO
            self.limit_key = 'snapshot_limit_auto'
        else:
            self.tt = TT_EXEC
            self.snaptype = Snapshot.MANUAL
            self.limit_key = 'snapshot_limit_manual'

        return apiview, detail

    def _update_note(self):
        # Changing snapshot note instead of rollback (not logging)
        request = self.request
        ser = SnapshotSerializer(request, self.snap, data=self.data, partial=True)

        if ser.is_valid():
            ser.object.save()
            return SuccessTaskResponse(request, ser.data, vm=self.vm)
        else:
            return FailureTaskResponse(request, ser.errors, vm=self.vm)

    def get(self):
        ser = SnapshotSerializer(self.request, self.snap)

        return SuccessTaskResponse(self.request, ser.data, vm=self.vm)

    def post(self):
        self._check_vm_status()
        apiview, detail = self._get_apiview_detail()
        request, vm, snap = self.request, self.vm, self.snap

        snap.status = snap.PENDING
        snap.define_id = self.snap_define_id
        snap.type = self.snaptype
        ser = SnapshotSerializer(request, snap, data=self.data)
        fsfreeze = ''

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, vm=vm)

        if vm.is_hvm() and self.data.get('fsfreeze', False):
            qga_socket = vm.qga_socket_path

            if qga_socket:
                snap.fsfreeze = True
                if vm.status != vm.STOPPED:
                    fsfreeze = '"%s"' % qga_socket

        self._check_snap_limit()
        self._check_snap_size_limit()  # Issue #chili-848
        self._check_snap_dc_size_limit()  # Issue #chili-848
        snap.zpool = vm.node.nodestorage_set.get(zpool=self.zpool)
        snap.save()
        detail += ', type=%s, fsfreeze=%s' % (self.snaptype, str(snap.fsfreeze).lower())
        msg = LOG_SNAP_CREATE
        lock = self.LOCK % (vm.uuid, snap.disk_id)
        cmd = 'esnapshot create "%s@%s" "es:snapname=%s" %s 2>&1' % (self.zfs_filesystem, snap.zfs_name, snap.name,
                                                                     fsfreeze)
        tid, err = execute(request, vm.owner.id, cmd, meta=snap_meta(vm, msg, apiview, detail), lock=lock,
                           callback=snap_callback(vm, snap), queue=vm.node.fast_queue, tt=self.tt)

        if err:
            snap.delete()
            return FailureTaskResponse(request, err, vm=vm)
        else:
            return TaskResponse(request, tid, msg=msg, vm=vm, api_view=apiview, detail=detail, data=self.data)

    def put(self):
        if 'note' in self.data:
            # Changing snapshot note instead of rollback (not logging)
            return self._update_note()

        request, vm, snap = self.request, self.vm, self.snap

        ser = SnapshotRestoreSerializer(request, vm, data=self.data)
        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors)

        target_vm, target_vm_disk_id = ser.target_vm, ser.target_vm_disk_id

        if vm.node.status not in vm.node.STATUS_OPERATIONAL:
            raise NodeIsNotOperational

        if target_vm.locked:
            raise VmIsLocked

        if target_vm != vm:
            if target_vm.node.status not in target_vm.node.STATUS_OPERATIONAL:
                raise NodeIsNotOperational

            self._check_vm_status(vm=target_vm)

            if not vm.has_compatible_brand(target_vm.brand):
                raise PreconditionRequired('VM brand mismatch')

            source_disk = vm.json_active_get_disks()[self.disk_id - 1]
            target_disk = target_vm.json_active_get_disks()[target_vm_disk_id - 1]

            if target_disk['size'] != source_disk['size']:
                raise PreconditionRequired('Disk size mismatch')

        self._check_vm_status()
        self._check_snap_status()
        apiview, detail = self._get_apiview_detail()
        apiview['force'] = ser.data['force']

        if target_vm != vm:
            detail += ", source_hostname='%s', target_hostname='%s', target_disk_id=%s" % (vm.hostname,
                                                                                           target_vm.hostname,
                                                                                           target_vm_disk_id)
            apiview['source_hostname'] = vm.hostname
            apiview['target_hostname'] = target_vm.hostname
            apiview['target_disk_id'] = target_vm_disk_id

            if not apiview['force']:
                if Snapshot.objects.only('id').filter(vm=target_vm, disk_id=ser.target_vm_real_disk_id).exists():
                    raise ExpectationFailed('Target VM has snapshots')

        elif not apiview['force']:
            snaplast = Snapshot.objects.only('id').filter(vm=vm, disk_id=snap.disk_id).order_by('-id')[0]
            if snap.id != snaplast.id:
                raise ExpectationFailed('VM has more recent snapshots')

        if target_vm.status != vm.STOPPED:
            raise VmIsNotOperational('VM is not stopped')

        if target_vm.tasks:
            raise VmHasPendingTasks

        msg = LOG_SNAP_UPDATE
        lock = self.LOCK % (vm.uuid, snap.disk_id)

        if target_vm == vm:
            cmd = 'esnapshot rollback "%s@%s" 2>&1' % (self.zfs_filesystem, snap.zfs_name)
        else:
            cmd = 'esbackup snap-restore -s %s@%s -d %s' % (self.zfs_filesystem, snap.zfs_name,
                                                            ser.target_vm_disk_zfs_filesystem)
            if vm.node != target_vm.node:
                cmd += ' -H %s' % target_vm.node.address

            vm.set_notready()

        target_vm.set_notready()
        tid, err = execute(request, target_vm.owner.id, cmd, meta=snap_meta(target_vm, msg, apiview, detail), lock=lock,
                           callback=snap_callback(target_vm, snap), queue=vm.node.fast_queue)

        if err:
            target_vm.revert_notready()
            if vm != target_vm:
                vm.revert_notready()
            return FailureTaskResponse(request, err, vm=target_vm)
        else:
            snap.save_status(snap.ROLLBACK)
            return TaskResponse(request, tid, msg=msg, vm=target_vm, api_view=apiview, detail=detail, data=self.data)

    def delete(self):
        self._check_vm_status()
        self._check_snap_status(lost_ok=True)
        request, vm, snap = self.request, self.vm, self.snap
        apiview, detail = self._get_apiview_detail()
        msg = LOG_SNAP_DELETE

        if snap.status == Snapshot.LOST:
            snap.delete()
            res = {'message': 'Snapshot successfully deleted from DB'}
            return SuccessTaskResponse(request, res, msg=msg, vm=vm, detail=detail)

        SnapshotSerializer(request, snap)
        lock = self.LOCK % (vm.uuid, snap.disk_id)
        cmd = 'esnapshot destroy "%s@%s" 2>&1' % (self.zfs_filesystem, snap.zfs_name)
        tid, err = execute(request, vm.owner.id, cmd, meta=snap_meta(vm, msg, apiview, detail), lock=lock,
                           callback=snap_callback(vm, snap), queue=vm.node.fast_queue, tt=self.tt)

        if err:
            return FailureTaskResponse(request, err, vm=vm)
        else:
            snap.save_status(snap.PENDING)
            return TaskResponse(request, tid, msg=msg, vm=vm, api_view=apiview, detail=detail, data=self.data)
