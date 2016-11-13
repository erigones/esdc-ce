from django.utils.translation import ugettext_noop as _

from api import status
from api.api_views import APIView
from api.exceptions import PreconditionRequired, ObjectAlreadyExists
from api.task.response import SuccessTaskResponse
from api.utils.db import get_object
from api.dc.utils import remove_dc_binding_virt_object
from api.dc.template.serializers import TemplateSerializer
from api.dc.messages import LOG_TEMPLATE_ATTACH, LOG_TEMPLATE_DETACH
from api.template.messages import LOG_TEMPLATE_UPDATE
from vms.models import VmTemplate


class DcTemplateView(APIView):
    serializer = TemplateSerializer
    order_by_default = order_by_fields = ('name',)

    def __init__(self, request, name, data):
        super(DcTemplateView, self).__init__(request)
        self.data = data
        self.name = name

        if name:
            attrs = {'name': name}

            if request.method != 'POST':
                attrs['dc'] = request.dc

            self.vmt = get_object(request, VmTemplate, attrs, sr=('owner', 'dc_bound'), exists_ok=True,
                                  noexists_fail=True)
        else:
            self.vmt = VmTemplate.objects.select_related('owner', 'dc_bound').filter(dc=request.dc)\
                                                                             .exclude(access__in=VmTemplate.INVISIBLE)\
                                                                             .order_by(*self.order_by)

    def get(self, many=False):
        if many or not self.name:
            if self.full:
                if self.vmt:
                    res = self.serializer(self.request, self.vmt, many=True).data
                else:
                    res = []
            else:
                res = list(self.vmt.values_list('name', flat=True))
        else:
            res = self.serializer(self.request, self.vmt).data

        return SuccessTaskResponse(self.request, res)

    def _remove_dc_binding(self, res):
        if self.vmt.dc_bound:
            remove_dc_binding_virt_object(res.data.get('task_id'), LOG_TEMPLATE_UPDATE, self.vmt,
                                          user=self.request.user)

    def post(self):
        dc, vmt = self.request.dc, self.vmt

        if vmt.dc.filter(id=dc.id).exists():
            raise ObjectAlreadyExists(model=VmTemplate)

        ser = self.serializer(self.request, vmt)
        vmt.dc.add(dc)
        res = SuccessTaskResponse(self.request, ser.data, obj=vmt, status=status.HTTP_201_CREATED,
                                  detail_dict=ser.detail_dict(), msg=LOG_TEMPLATE_ATTACH)
        self._remove_dc_binding(res)

        return res

    def delete(self):
        dc, vmt = self.request.dc, self.vmt

        if dc.vm_set.filter(template=vmt).exists():
            raise PreconditionRequired(_('Template is used by some VMs'))

        ser = self.serializer(self.request, vmt)
        vmt.dc.remove(dc)
        res = SuccessTaskResponse(self.request, None, obj=vmt, detail_dict=ser.detail_dict(), msg=LOG_TEMPLATE_DETACH)
        self._remove_dc_binding(res)

        return res
