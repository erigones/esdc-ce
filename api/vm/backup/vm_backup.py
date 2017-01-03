from django.utils.translation import ugettext_noop as _

from vms.models import Snapshot, BackupDefine, Backup
from que import TT_EXEC, TT_AUTO
from api.api_views import TaskAPIView
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.exceptions import (VmIsNotOperational, NodeIsNotOperational, PreconditionRequired, ExpectationFailed,
                            ObjectNotFound, VmHasPendingTasks, VmIsLocked)
from api.utils.db import get_object
from api.vm.utils import get_vm
from api.vm.messages import LOG_BKP_CREATE, LOG_BKP_UPDATE, LOG_BKP_DELETE
from api.vm.backup.serializers import BackupSerializer, BackupRestoreSerializer
from api.vm.backup.utils import BACKUP_TASK_EXPIRES, get_backup_cmd
from api.vm.snapshot.utils import get_disk_id, filter_disk_id


class VmBackup(TaskAPIView):
    """
    api.vm.backup.views.vm_backup
    """
    LOCK = 'vm_backup vm:%s disk:%s'

    def __init__(self, request, hostname_or_uuid, bkpname, data):
        super(VmBackup, self).__init__(request)

        if request.method == 'POST':  # Got bkpdef instead of bkpname
            vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True)
            disk_id, real_disk_id, zfs_filesystem = get_disk_id(request, vm, data)
            # TODO: check indexes
            define = get_object(request, BackupDefine, {'name': bkpname, 'vm': vm, 'disk_id': real_disk_id},
                                exists_ok=True, noexists_fail=True, sr=('vm', 'node'))
            bkpname = define.generate_backup_name()
            bkp_get = {'name': bkpname, 'vm_hostname': vm.hostname, 'vm_disk_id': disk_id - 1, 'vm': vm}

        else:
            try:
                if 'hostname' in data:  # Force original hostname
                    raise ObjectNotFound
                # Only target VM status and backup node status are important
                vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True, check_node_status=None)
            except ObjectNotFound:
                vm = None
                bkp_get = {'name': bkpname, 'vm_hostname': hostname_or_uuid}
            else:
                bkp_get = {'vm': vm, 'name': bkpname}

            define = None
            real_disk_id = None
            zfs_filesystem = None
            bkp_get = filter_disk_id(None, bkp_get, data, default=1)  # vm_disk_id instead of disk_id

        bkp_get['dc'] = request.dc
        # Backup instance
        self.bkp = bkp = get_object(request, Backup, bkp_get, sr=('node', 'define', 'vm'))
        self.disk_id = bkp.array_disk_id
        self.hostname = bkp.vm_hostname_real
        self.define = define
        self.real_disk_id = real_disk_id
        self.zfs_filesystem = zfs_filesystem
        self.vm = vm
        self.data = data

        # Task type (a = automatic, e = manual)
        if getattr(request, 'define_id', None):
            self.tt = TT_AUTO
        else:
            self.tt = TT_EXEC

    def _check_vm(self, vm):
        # Basic checks when working with online vm
        if not (self.request.user.is_admin(self.request) or vm.is_installed()):
            raise PreconditionRequired('VM is not installed')

        if vm.status not in (vm.RUNNING, vm.STOPPED, vm.STOPPING):
            raise VmIsNotOperational

    def _check_bkp_node(self):
        node = self.bkp.node
        if node.status != node.ONLINE:
            raise NodeIsNotOperational

    def _check_bkp(self, lost_ok=False):
        if not (self.bkp.status == Backup.OK or (lost_ok and self.bkp.status == Backup.LOST)):
            raise ExpectationFailed('VM backup status is not OK')

    def _check_bkp_dc_size_limit(self):
        """Issue #chili-848"""
        bkp = self.bkp
        limit = bkp.dc.settings.VMS_VM_BACKUP_DC_SIZE_LIMIT

        if limit is not None:
            limit = int(limit)
            total = Backup.get_total_dc_size(bkp.dc)

            if total >= limit:
                raise ExpectationFailed('DC backup size limit reached')

    def _meta(self):
        bkp = self.bkp
        # noinspection PyProtectedMember
        return {
            'output': {'returncode': 'returncode', 'stdout': 'json', 'stderr': 'message', 'detail': self.detail},
            'replace_stderr': ((bkp.vm_uuid, bkp.vm_hostname),),
            'msg': self.msg,
            'apiview': self.apiview,
            self.obj._pk_key: self.obj.pk,
        }

    def _callback(self):
        # noinspection PyProtectedMember
        return 'api.vm.backup.tasks.vm_backup_cb', {self.obj._pk_key: self.obj.pk, 'bkp_id': self.bkp.pk}

    def _apiview(self):
        return {'view': 'vm_backup', 'method': self.request.method, 'hostname': self.hostname,
                'disk_id': self.disk_id, 'bkpname': self.bkp.name, 'vm': bool(self.bkp.vm)}

    def _detail(self):
        detail = "hostname='%s', bkpname='%s', disk_id=%s" % (self.bkp.vm_hostname, self.bkp.name, self.disk_id)

        if self.request.method == 'POST':
            detail += ', fsfreeze=%s' % str(self.bkp.fsfreeze).lower()

        return detail

    def save_note(self):
        request = self.request
        ser = BackupSerializer(request, self.bkp, data=self.data, partial=True)

        if ser.is_valid():
            ser.object.save()
            return SuccessTaskResponse(request, ser.data)
        else:
            return FailureTaskResponse(request, ser.errors)

    def execute(self, cmd, **kwargs):
        super(VmBackup, self).execute(cmd, meta=self._meta(), callback=self._callback(), tt=self.tt,
                                      queue=self.bkp.node.backup_queue, expires=BACKUP_TASK_EXPIRES, **kwargs)
        return not bool(self.error)

    def get(self):
        return SuccessTaskResponse(self.request, BackupSerializer(self.request, self.bkp).data)

    def post(self):
        bkp, vm, define = self.bkp, self.vm, self.define
        bkp.disk_id = self.real_disk_id
        bkp.dc = vm.dc
        bkp.vm = vm
        bkp.json = vm.json_active
        bkp.define = define
        bkp.node = define.node
        bkp.zpool = define.zpool
        bkp.type = define.type
        bkp.status = bkp.PENDING
        ser = BackupSerializer(self.request, bkp, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, vm=vm)

        if define.fsfreeze:  # Store in self.fsfreeze, because it is displayed in response/tasklog detail
            qga_socket = vm.qga_socket_path
            if qga_socket:
                bkp.fsfreeze = True
                if vm.status == vm.STOPPED:
                    qga_socket = None
        else:
            qga_socket = None

        self._check_bkp_dc_size_limit()  # Issue #chili-848
        self._check_vm(vm)
        self.obj = vm
        self._check_bkp_node()
        bkp.save()
        self.msg = LOG_BKP_CREATE

        if self.execute(get_backup_cmd('create', bkp, define=define, zfs_filesystem=self.zfs_filesystem,
                                       fsfreeze=qga_socket),
                        lock=self.LOCK % (vm.uuid, bkp.disk_id)):
            return self.task_response

        bkp.delete()
        return self.error_response

    def put(self):
        if 'note' in self.data:  # Changing backup note instead of restore (not logging!)
            return self.save_note()

        ser = BackupRestoreSerializer(data=self.data)
        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors)

        self._check_bkp()
        self._check_bkp_node()

        # Prepare vm for restore
        request, bkp = self.request, self.bkp

        vm = get_vm(request, ser.data['target_hostname_or_uuid'], exists_ok=True, noexists_fail=True,
                    check_node_status=None)

        if vm.node.status not in vm.node.STATUS_OPERATIONAL:
            raise NodeIsNotOperational

        if vm.locked:
            raise VmIsLocked

        if vm.brand != bkp.vm_brand:
            raise PreconditionRequired('VM brand mismatch')

        disk_id, real_disk_id, zfs_filesystem = get_disk_id(request, vm, self.data, key='target_disk_id',
                                                            default=None)
        tgt_disk = vm.json_active_get_disks()[disk_id - 1]

        if tgt_disk['size'] != bkp.disk_size:
            raise PreconditionRequired('Disk size mismatch')

        target_ns = vm.get_node_storage(real_disk_id)
        # The backup is first restored to a temporary dataset, so it is required to have as much free space
        # as the backup size (which we don't have -> so we use the backup disk size [pessimism])
        if bkp.disk_size > target_ns.storage.size_free:
            raise PreconditionRequired('Not enough free space on target storage')

        if not ser.data['force'] and Snapshot.objects.only('id').filter(vm=vm, disk_id=real_disk_id).exists():
            raise ExpectationFailed('VM has snapshots')

        if vm.status != vm.STOPPED:
            raise VmIsNotOperational(_('VM is not stopped'))

        if vm.tasks:
            raise VmHasPendingTasks

        self.msg = LOG_BKP_UPDATE
        self.obj = vm
        # Cache apiview and detail
        # noinspection PyUnusedLocal
        apiview = self.apiview
        # noinspection PyUnusedLocal
        detail = self.detail
        self._detail_ += ", target_hostname='%s', target_disk_id=%s" % (vm.hostname, disk_id)
        self._apiview_['target_hostname'] = vm.hostname
        self._apiview_['target_disk_id'] = disk_id
        self._apiview_['force'] = ser.data['force']

        if bkp.vm:
            self._apiview_['source_hostname'] = bkp.vm.hostname
        else:
            self._apiview_['source_hostname'] = ''

        vm.set_notready()

        if self.execute(get_backup_cmd('restore', bkp, zfs_filesystem=zfs_filesystem, vm=vm),
                        lock=self.LOCK % (vm.uuid, disk_id)):
            bkp.save_status(bkp.RESTORE)
            return self.task_response

        vm.revert_notready()
        return self.error_response

    def delete(self):
        self._check_bkp(lost_ok=True)
        self._check_bkp_node()

        bkp = self.bkp
        vm = bkp.vm  # Can be None, because this can be a backup for already deleted VM
        self.msg = LOG_BKP_DELETE

        if vm:
            self._check_vm(vm)
            self.obj = vm
        else:
            self.obj = bkp.node

        if bkp.status == Backup.LOST:
            bkp.delete()
            res = {'message': 'Backup successfully deleted from DB'}
            return SuccessTaskResponse(self.request, res, msg=LOG_BKP_DELETE, vm=vm, detail=self._detail())

        if self.execute(get_backup_cmd('delete', bkp), lock=self.LOCK % (bkp.vm_uuid, bkp.disk_id)):
            bkp.save_status(bkp.PENDING)
            return self.task_response

        return self.error_response
