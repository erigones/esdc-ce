from api.api_views import APIView
from api.utils.db import get_virt_object
from api.task.response import SuccessTaskResponse
from api.node.vm.serializers import VmSerializer
from api.node.vm.utils import get_vms
from vms.models import VmTemplate


class TemplateVmView(APIView):
    """
    api.template.vm.views.template_vm_list
    """
    dc_bound = False
    order_by_default = order_by_fields = ('hostname',)

    def __init__(self, request, name, data):
        super(TemplateVmView, self).__init__(request)
        self.name = name
        self.data = data
        self.template = get_virt_object(request, VmTemplate, data=data, name=name)

    def get(self, many=True):
        """Display list of VMs that use a specific template"""
        assert many  # Currently only used for displaying list of VMs

        vms = get_vms(self.request, order_by=self.order_by, slavevm__isnull=True, template=self.template)

        if self.full or self.extended:
            res = VmSerializer(self.request, vms.select_related('owner', 'node', 'dc'), many=True).data
        else:
            res = vms.values_list('hostname', flat=True)

        return SuccessTaskResponse(self.request, res, dc_bound=self.dc_bound)
