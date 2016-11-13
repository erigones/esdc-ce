from django.utils.translation import ugettext_lazy as _

from api.api_views import APIView
from api.exceptions import PreconditionRequired
from api.status import HTTP_201_CREATED
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.utils.db import get_virt_object
from api.template.base.serializers import TemplateSerializer, ExtendedTemplateSerializer
from api.template.messages import LOG_TEMPLATE_CREATE, LOG_TEMPLATE_UPDATE, LOG_TEMPLATE_DELETE
from api.dc.utils import attach_dc_virt_object
from api.dc.messages import LOG_TEMPLATE_ATTACH
from vms.models import VmTemplate


class TemplateView(APIView):
    dc_bound = False
    order_by_default = order_by_fields = ('name',)
    order_by_field_map = {'created': 'id'}

    def __init__(self, request, name, data):
        super(TemplateView, self).__init__(request)
        self.data = data
        self.name = name

        if self.extended:
            pr = ('dc',)
            self.ser_class = ExtendedTemplateSerializer
        else:
            pr = ()
            self.ser_class = TemplateSerializer

        self.template = get_virt_object(request, VmTemplate, data=data, pr=pr, many=not name, name=name,
                                        order_by=self.order_by)

    def get(self, many=False):
        if many or not self.name:
            if self.full or self.extended:
                if self.template:
                    res = self.ser_class(self.request, self.template, many=True).data
                else:
                    res = []
            else:
                res = list(self.template.values_list('name', flat=True))
        else:
            res = self.ser_class(self.request, self.template).data

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    def post(self):
        template, request = self.template, self.request

        if not request.user.is_staff:
            self.data.pop('dc_bound', None)  # default DC binding cannot be changed when creating object

        template.owner = request.user  # just a default
        template.alias = template.name  # just a default
        ser = TemplateSerializer(request, template, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=template, dc_bound=False)

        ser.object.save()
        res = SuccessTaskResponse(request, ser.data, status=HTTP_201_CREATED, obj=template, dc_bound=False,
                                  detail_dict=ser.detail_dict(), msg=LOG_TEMPLATE_CREATE)

        if template.dc_bound:
            attach_dc_virt_object(res.data.get('task_id'), LOG_TEMPLATE_ATTACH, template, template.dc_bound,
                                  user=request.user)

        return res

    def put(self):
        template = self.template
        ser = TemplateSerializer(self.request, template, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=template, dc_bound=False)

        ser.object.save()

        return SuccessTaskResponse(self.request, ser.data, obj=template, detail_dict=ser.detail_dict(),
                                   msg=LOG_TEMPLATE_UPDATE, dc_bound=False)

    def delete(self):
        template = self.template
        ser = TemplateSerializer(self.request, template)

        if template.vm_set.exists():
            raise PreconditionRequired(_('Template is used by some VMs'))

        owner = template.owner
        obj = template.log_list
        ser.object.delete()

        return SuccessTaskResponse(self.request, None, obj=obj, owner=owner, msg=LOG_TEMPLATE_DELETE, dc_bound=False)
