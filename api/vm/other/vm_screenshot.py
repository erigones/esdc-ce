from logging import getLogger

from que.tasks import execute
from api.api_views import APIView
from api.exceptions import VmIsNotOperational, OperationNotSupported
from api.task.response import SuccessTaskResponse, FailureTaskResponse, TaskResponse
from api.vm.utils import get_vm

logger = getLogger(__name__)


class VmScreenshot(APIView):
    """
    api.vm.other.views.vm_screenshot
    """
    def __init__(self, request, hostname_or_uuid, data):
        super(VmScreenshot, self).__init__(request)
        self.hostname_or_uuid = hostname_or_uuid
        self.data = data
        self.vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True)

    def get(self):
        vm = self.vm

        if not vm.is_kvm():
            raise OperationNotSupported

        result = {'image': vm.screenshot}

        if result['image']:
            return SuccessTaskResponse(self.request, result, vm=vm)
        else:
            return FailureTaskResponse(self.request, result, vm=vm)

    def post(self):
        request, vm = self.request, self.vm

        if not self.vm.is_kvm():
            raise OperationNotSupported

        if vm.status not in (vm.RUNNING, vm.STOPPING):
            raise VmIsNotOperational

        apiview = {'view': 'vm_screenshot', 'method': request.method, 'hostname': vm.hostname}
        cmd = 'vmadm sysrq %s nmi >&2 && sleep 0.5 && vmadm sysrq %s screenshot >&2 && \
cat /%s/%s/root/tmp/vm.ppm' % (vm.uuid, vm.uuid, vm.zpool, vm.uuid)
        lock = 'vm_screenshot vm:%s' % vm.uuid
        meta = {'output': {'returncode': 'returncode', 'stderr': 'message', 'stdout': 'image'},
                'replace_stderr': ((vm.uuid, vm.hostname),),
                'encode_stdout': True, 'compress_stdout': True, 'apiview': apiview}
        callback = ('api.vm.other.tasks.vm_screenshot_cb', {'vm_uuid': vm.uuid})

        tid, err = execute(request, vm.owner.id, cmd, meta=meta, lock=lock, callback=callback, queue=vm.node.fast_queue)
        if err:
            return FailureTaskResponse(request, err, vm=vm)
        else:
            return TaskResponse(request, tid, vm=vm, api_view=apiview, data=self.data)  # No msg
