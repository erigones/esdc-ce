from api.api_views import APIView, TaskAPIView
from api.task.response import SuccessTaskResponse
from api.node.messages import LOG_VM_HARVEST
from api.node.vm.utils import get_vms
from api.node.vm.serializers import VmSerializer, ExtendedVmSerializer


class NodeVmView(APIView):
    """
    api.node.vm.base.views.node_vm_list
    """
    dc_bound = False
    order_by_default = order_by_fields = ('hostname',)

    def __init__(self, request, node, data):
        super(NodeVmView, self).__init__(request)
        self.node = node
        self.data = data

    def get(self, many=True):
        """Display list of VMs + do not hide replicated-slave VMs"""
        assert many  # Currently only used for displaying list of VMs

        sr = ['owner', 'node', 'dc']

        if self.extended:
            ser_class = ExtendedVmSerializer
            extra = {'select': ExtendedVmSerializer.extra_select}
            sr.append('slavevm')
        else:
            ser_class = VmSerializer
            extra = None

        if self.full or self.extended:
            vms = get_vms(self.request, sr=sr, order_by=self.order_by, node=self.node)

            if self.extended:
                # noinspection PyArgumentList
                vms = vms.extra(**extra).prefetch_related('tags')

            if vms:
                # noinspection PyUnresolvedReferences
                res = ser_class(self.request, vms, many=True).data
            else:
                res = []
        else:
            res = list(get_vms(self.request, sr=(), order_by=self.order_by, node=self.node).values_list('hostname',
                                                                                                        flat=True))

        return SuccessTaskResponse(self.request, res, dc_bound=self.dc_bound)


class VmHarvestView(TaskAPIView):
    """
    Used by api.node.vm.views.harvest_vm.
    """
    def __init__(self, request, node, vm_uuid=None):
        super(TaskAPIView, self).__init__(request)
        self.node = self.obj = node
        self.vm = vm_uuid

    def _apiview(self):
        return {'view': 'harvest_vm', 'method': self.request.method, 'hostname': self.node.hostname, 'vm': self.vm}

    def _detail(self):
        if self.vm:
            return 'vm=%s' % self.vm
        return ''

    def post(self):
        self.msg = LOG_VM_HARVEST

        if self.vm:
            cmd = "vmadm get %s 2> /dev/null; echo '||||'" % self.vm
        else:
            cmd = "for vm in `vmadm list -p -H -o uuid`; do vmadm get $vm; echo '||||'; done"

        if self.execute(cmd, callback=('api.node.vm.tasks.harvest_vm_cb', {'node_uuid': self.node.uuid}),
                        meta=self._meta(), lock='harvest_vm', queue=self.node.fast_queue):
            return self.task_response
        return self.error_response
