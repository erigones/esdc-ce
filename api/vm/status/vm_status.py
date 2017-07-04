from logging import getLogger

from django.conf import settings

from que.tasks import execute
from que.utils import task_id_from_request
from vms.models import Vm
from api.api_views import APIView
from api.exceptions import (PermissionDenied, VmIsNotOperational, NodeIsNotOperational, PreconditionRequired,
                            ExpectationFailed)
from api.serializers import ForceSerializer
from api.task.response import SuccessTaskResponse, FailureTaskResponse, TaskResponse
from api.vm.utils import get_vms, get_vm
from api.vm.messages import (LOG_STATUS_GET, LOG_START, LOG_START_ISO, LOG_START_UPDATE, LOG_START_UPDATE_ISO,
                             LOG_STOP, LOG_STOP_FORCE, LOG_REBOOT, LOG_REBOOT_FORCE)
from api.vm.status.tasks import vm_status_changed
from api.vm.status.serializers import (VmStatusSerializer, VmStatusActionIsoSerializer, VmStatusFreezeSerializer,
                                       VmStatusUpdateJSONSerializer)

logger = getLogger(__name__)


class VmStatus(APIView):
    """
    api.vm.status.views.vm_status
    """
    order_by_default = order_by_fields = ('hostname',)
    detail = ''
    actions = ('start', 'stop', 'reboot', 'current')
    statuses = (Vm.RUNNING, Vm.STOPPED, Vm.STOPPING, Vm.FROZEN, Vm.NOTREADY_STOPPED, Vm.NOTREADY_RUNNING)

    def __init__(self, request, hostname_or_uuid, action, data):
        super(VmStatus, self).__init__(request)
        self.hostname_or_uuid = hostname_or_uuid
        self.action = action
        self.data = data

        if hostname_or_uuid:
            self.vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True, sr=('node', 'owner'))
        else:
            self.vm = get_vms(request, sr=('node', 'owner'), order_by=self.order_by)

    @property
    def zonecfg(self):
        """SmartOS VM zone configuration. Called after VM is created."""
        cfg = 'add fs;set dir=%s;set special=/iso;set type=lofs;add options [ro,nodevices];end' % settings.VMS_ISO_DIR
        return "zonecfg -z %s '%s' >/dev/null 2>/dev/null" % (self.vm.uuid, cfg)

    @property
    def apiview(self):
        return {'view': 'vm_status', 'method': self.request.method, 'action': self.action, 'hostname': self.vm.hostname}

    def _action_cmd(self, action, force=False):
        cmd = 'vmadm %s %s' % (action, self.vm.uuid)
        if force:
            cmd += ' -F'
        return cmd

    def _stop_cmd(self, force=False):
        return self._action_cmd('stop', force=force)

    def _reboot_cmd(self, force=False):
        return self._action_cmd('stop', force=force)

    def _start_cmd(self, iso=None, iso2=None, once=False):
        vm = self.vm
        cmd = ['vmadm start %(uuid)s']

        if iso:
            self.detail = 'cdimage=%s' % iso.name
            cmd_dict = {
                'uuid': vm.uuid,
                'iso_path': '/%s/%s/root/iso' % (vm.zpool, vm.uuid),
                'iso_dir': settings.VMS_ISO_DIR,
                'iso_name': iso.name,
                'zonecfg': self.zonecfg,
            }
            touch = '%(zonecfg)s; mkdir -p "%(iso_path)s"; test -f "%(iso_dir)s/%(iso_name)s" && ' \
                    'touch %(iso_path)s/%(iso_name)s || (rm -f %(iso_path)s/%(iso_name)s; ' \
                    'echo "ISO image %(iso_name)s is not available on compute node" >&2; exit 9) &&'

            if once:
                cmd.append('order=c,once=d cdrom=/iso/%(iso_name)s,ide')
                vm.last_cdimage = None
            else:
                cmd.append('order=d cdrom=/iso/%(iso_name)s,ide')
                vm.last_cdimage = iso.name

            if iso2:
                self.detail += ' cdimage2=%s' % iso2.name
                cmd_dict['iso2_name'] = iso2.name
                touch += '(test -f "%(iso_dir)s/%(iso2_name)s" && ' \
                         'touch %(iso_path)s/%(iso2_name)s || rm -f %(iso_path)s/%(iso2_name)s) >/dev/null 2>/dev/null;'
                cmd.append('cdrom=/iso/%(iso2_name)s,ide')

            cmd.insert(0, touch)

        else:
            cmd_dict = {'uuid': vm.uuid}
            cmd.append('order=c')
            vm.last_cdimage = None

        return ' '.join(cmd) % cmd_dict

    def get_current_status(self):
        """Get current VM status"""
        request, vm = self.request, self.vm
        force = self.data.get('force', False)

        if vm.node.status not in vm.node.STATUS_OPERATIONAL:
            raise NodeIsNotOperational

        apiview = self.apiview
        msg = LOG_STATUS_GET
        cmd = 'vmadm list -p -H -o state uuid=' + vm.uuid
        meta = {
            'output': {'returncode': 'returncode', 'stdout': 'stdout', 'stderr': 'stderr', 'hostname': vm.hostname},
            'msg': msg,
            'vm_uuid': vm.uuid,
            'apiview': apiview,
            'last_status': vm.status,
        }
        callback = (
            'api.vm.status.tasks.vm_status_current_cb',
            {'vm_uuid': vm.uuid, 'force_change': force}
        )

        tid, err = execute(request, vm.owner.id, cmd, meta=meta, callback=callback, queue=vm.node.fast_queue,
                           nolog=True)

        if err:
            return FailureTaskResponse(request, err, vm=vm)
        else:
            return TaskResponse(request, tid, vm=vm, api_view=apiview, data=self.data)  # No msg

    def get(self, many=False):
        request, vm = self.request, self.vm

        if many or not self.hostname_or_uuid:
            if vm:
                res = VmStatusSerializer(vm, many=True).data
            else:
                res = []
            return SuccessTaskResponse(request, res)

        if self.action == 'current':
            if vm.status not in (Vm.RUNNING, Vm.STOPPED, Vm.STOPPING, Vm.ERROR):
                raise VmIsNotOperational
            else:
                return self.get_current_status()
        else:
            ser = VmStatusSerializer(vm)
            return SuccessTaskResponse(request, ser.data, vm=vm)

    def put(self):
        request, vm, action = self.request, self.vm, self.action

        # for PUT /current/ action user needs to be SuperAdmin
        # since this operation will forcibly change whatever status a VM has in the DB
        if action == 'current' and not request.user.is_super_admin(request):
            raise PermissionDenied

        # Cannot change status unless the VM is created on node
        if vm.status not in self.statuses and action != 'current':
            raise VmIsNotOperational

        if action not in self.actions:
            raise ExpectationFailed('Bad action')

        apiview = self.apiview
        f_ser = VmStatusFreezeSerializer(data=self.data)

        if f_ser.is_valid():
            freeze = apiview['freeze'] = f_ser.data['freeze']
            unfreeze = apiview['unfreeze'] = f_ser.data['unfreeze']
        else:
            return FailureTaskResponse(request, f_ser.errors, vm=vm)

        if ((action == 'start' and vm.status == Vm.STOPPED and not freeze) or
                (action == 'reboot' and vm.status == Vm.RUNNING and not freeze) or
                (action == 'stop' and vm.status in (Vm.STOPPING, Vm.RUNNING))):
            pass

        elif action == 'stop' and vm.status == Vm.STOPPED and freeze:
            if not request.user.is_admin(request):
                raise PermissionDenied

            tid = task_id_from_request(request, owner_id=vm.owner.id, dummy=True)
            vm_status_changed(tid, vm, vm.FROZEN, save_state=True)
            res = {'message': 'VM %s is already stopped. Changing status to frozen.' % vm.hostname}

            return SuccessTaskResponse(request, res, task_id=tid, vm=vm)

        elif action == 'stop' and vm.status == Vm.FROZEN and unfreeze:
            if not request.user.is_admin(request):
                raise PermissionDenied

            tid = task_id_from_request(request, owner_id=vm.owner.id, dummy=True)
            vm_status_changed(tid, vm, vm.STOPPED, save_state=True)
            res = {'message': 'Removing frozen status for VM %s.' % vm.hostname}

            return SuccessTaskResponse(request, res, task_id=tid, vm=vm)

        elif action == 'current':
            if not self.data.get('force', False):
                raise ExpectationFailed('Force parameter must be used!')
            return self.get_current_status()

        else:
            raise ExpectationFailed('Bad action')

        dc_settings = request.dc.settings

        if action in ('stop', 'reboot') and vm.uuid in dc_settings.VMS_NO_SHUTDOWN:
            raise PreconditionRequired('Internal VM can\'t be stopped')

        lock = 'vm_status vm:%s' % vm.uuid
        stdin = None
        apiview['update'] = False
        transition_to_stopping = False

        if action == 'start':
            msg = LOG_START
            ser = VmStatusActionIsoSerializer(request, vm, data=self.data)

            if not ser.is_valid():
                return FailureTaskResponse(request, ser.errors, vm=vm)

            if ser.data and ser.iso:
                if not request.user.is_admin(request) and vm.is_installed() and \
                        (ser.iso.name != dc_settings.VMS_ISO_RESCUECD):
                    raise PreconditionRequired('VM is not installed')

                msg = LOG_START_ISO
                iso = ser.iso
                cmd = self._start_cmd(iso=iso, iso2=ser.iso2, once=ser.data['cdimage_once'])
            else:
                iso = None
                cmd = self._start_cmd()

            ser_update = VmStatusUpdateJSONSerializer(data=self.data)

            if ser_update.is_valid():
                if vm.json_changed():
                    apiview['update'] = ser_update.data['update']
                    logger.info('VM %s json != json_active', vm)

                    if apiview['update']:
                        from api.vm.base.vm_manage import VmManage
                        stdin, os_cmd = VmManage.fix_update(vm.json_update())
                        stdin = stdin.dump()

                        if os_cmd:  # Dangerous, explicit update needed
                            # TODO: fix in gui
                            raise PreconditionRequired('VM must be updated first')

                        if iso:
                            msg = LOG_START_UPDATE_ISO
                        else:
                            msg = LOG_START_UPDATE

                        cmd_update = 'vmadm update %s >&2; e=$?; vmadm get %s 2>/dev/null; ' % (vm.uuid, vm.uuid)
                        cmd = cmd_update + cmd + '; exit $e'
                        # logger.info('VM %s json_active is going to be updated with json """%s"""', vm, stdin)
                    else:
                        logger.warning('VM %s json_active update disabled', vm)

            else:
                return FailureTaskResponse(request, ser_update.errors, vm=vm)

        else:
            force = ForceSerializer(data=self.data, default=False).is_true()
            cmd = self._action_cmd(action, force=force)

            if action == 'reboot':
                msg = LOG_REBOOT
            else:
                msg = LOG_STOP

            if force:
                apiview['force'] = True

                if action == 'reboot':
                    msg = LOG_REBOOT_FORCE
                else:
                    lock += ' force'
                    msg = LOG_STOP_FORCE

            elif vm.status == Vm.STOPPING:
                raise VmIsNotOperational('VM is already stopping; try to use force')
            else:
                transition_to_stopping = True

        meta = {
            'output': {'returncode': 'returncode', 'stderr': 'message', 'stdout': 'json'},
            'replace_stderr': ((vm.uuid, vm.hostname),),
            'detail': self.detail,
            'msg': msg,
            'vm_uuid': vm.uuid,
            'apiview': apiview,
            'last_status': vm.status,
        }
        callback = ('api.vm.status.tasks.vm_status_cb', {'vm_uuid': vm.uuid})

        tid, err = execute(request, vm.owner.id, cmd, stdin=stdin, meta=meta,
                           lock=lock, callback=callback, queue=vm.node.fast_queue)

        if err:
            return FailureTaskResponse(request, err, vm=vm)
        else:
            if transition_to_stopping:
                vm.save_status(Vm.STOPPING)

            return TaskResponse(request, tid, msg=msg, vm=vm, api_view=apiview, detail=self.detail, data=self.data,
                                api_data={'status': vm.status, 'status_display': vm.status_display()})
