from logging import getLogger

from api.api_views import APIView
from api.exceptions import VmIsNotOperational, OperationNotSupported, InvalidInput
from api.task.response import FailureTaskResponse, TaskResponse
from api.vm.utils import get_vm
from api.vm.messages import LOG_QGA_COMMAND
from api.vm.qga.serializers import VmQGASerializer
from que.tasks import execute
from bin.eslib.qga import COMMANDS

logger = getLogger(__name__)


class VmQGA(APIView):
    """
    api.vm.qga.views.vm_qga
    """
    def __init__(self, request, hostname_or_uuid, command, data):
        super(VmQGA, self).__init__(request)
        self.hostname_or_uuid = hostname_or_uuid
        self.command = command
        self.data = data
        self.vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True)

    def put(self):
        request, vm, command = self.request, self.vm, self.command

        if not vm.is_kvm():
            raise OperationNotSupported

        if vm.status not in (vm.RUNNING, vm.STOPPING):
            raise VmIsNotOperational

        if command not in COMMANDS:
            raise InvalidInput('Invalid command')

        ser = VmQGASerializer(request, command, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=vm)

        apiview = {
            'view': 'vm_qga',
            'method': request.method,
            'hostname': vm.hostname,
            'command': command,
        }
        cmd = 'qga-client %s %s 2>&1' % (vm.qga_socket_path, ' '.join(ser.get_full_command()))
        lock = 'vm_qga vm:%s' % vm.uuid
        meta = {
            'output': {'returncode': 'returncode', 'stdout': 'message'},
            'replace_stdout': ((vm.uuid, vm.hostname),),
            'apiview': apiview,
            'msg': LOG_QGA_COMMAND,
            'vm_uuid': vm.uuid,
            'check_returncode': True,
        }

        # callback=None means that an implicit LOGTASK callback will be used (task_log_cb)
        tid, err = execute(request, vm.owner.id, cmd, meta=meta, lock=lock, queue=vm.node.fast_queue)

        if err:
            return FailureTaskResponse(request, err, vm=vm)
        else:
            return TaskResponse(request, tid, msg=LOG_QGA_COMMAND, obj=vm, api_view=apiview, data=self.data,
                                detail_dict=ser.detail_dict())
