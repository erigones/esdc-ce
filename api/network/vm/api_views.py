from api.api_views import APIView
from api.utils.db import get_virt_object
from api.task.response import SuccessTaskResponse
from api.node.vm.serializers import VmSerializer
from api.node.vm.utils import get_vms
from vms.models import Subnet


class NetworkVmView(APIView):
    """
    api.network.vm.views.net_vm_list
    """
    dc_bound = False
    order_by_default = order_by_fields = ('hostname',)

    def __init__(self, request, name, data):
        super(NetworkVmView, self).__init__(request)
        self.name = name
        self.data = data
        self.net = get_virt_object(request, Subnet, data=data, name=name)

    def get(self, many=True):
        """Display list of VMs that use a specific network"""
        assert many  # Currently only used for displaying list of VMs

        request, net = self.request, self.net

        if self.full or self.extended:
            sr = ('owner', 'node', 'dc')
        else:
            sr = ()

        vms = [vm for vm in get_vms(request, sr=sr, order_by=self.order_by, dc__in=net.dc.all(), slavevm__isnull=True)
               if net.uuid in vm.get_network_uuids()]

        if self.full or self.extended:
            res = VmSerializer(request, vms, many=True).data
        else:
            res = [vm.hostname for vm in vms]

        return SuccessTaskResponse(request, res, dc_bound=self.dc_bound)
