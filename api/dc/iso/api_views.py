from api import status
from api.api_views import APIView
from api.exceptions import ObjectAlreadyExists
from api.task.response import SuccessTaskResponse
from api.utils.db import get_object
from api.dc.utils import remove_dc_binding_virt_object
from api.dc.iso.serializers import IsoSerializer
from api.dc.messages import LOG_ISO_ATTACH, LOG_ISO_DETACH
from api.iso.messages import LOG_ISO_UPDATE
from vms.models import Iso


class DcIsoView(APIView):
    serializer = IsoSerializer
    order_by_default = order_by_fields = ('name',)

    def __init__(self, request, name, data):
        super(DcIsoView, self).__init__(request)
        self.data = data
        self.name = name

        if name:
            attrs = {'name': name}

            if request.method != 'POST':
                attrs['dc'] = request.dc

            self.iso = get_object(request, Iso, attrs, sr=('owner', 'dc_bound'), exists_ok=True, noexists_fail=True)
        else:
            self.iso = Iso.objects.select_related('owner', 'dc_bound').filter(dc=request.dc)\
                                                                      .exclude(access__in=Iso.INVISIBLE)\
                                                                      .order_by(*self.order_by)

    def get(self, many=False):
        if many or not self.name:
            if self.full:
                if self.iso:
                    res = self.serializer(self.request, self.iso, many=True).data
                else:
                    res = []
            else:
                res = list(self.iso.values_list('name', flat=True))
        else:
            res = self.serializer(self.request, self.iso).data

        return SuccessTaskResponse(self.request, res)

    def _remove_dc_binding(self, res):
        if self.iso.dc_bound:
            remove_dc_binding_virt_object(res.data.get('task_id'), LOG_ISO_UPDATE, self.iso, user=self.request.user)

    def post(self):
        dc, iso = self.request.dc, self.iso

        if iso.dc.filter(id=dc.id).exists():
            raise ObjectAlreadyExists(model=Iso)

        ser = self.serializer(self.request, iso)
        iso.dc.add(dc)
        res = SuccessTaskResponse(self.request, ser.data, obj=iso, status=status.HTTP_201_CREATED,
                                  detail_dict=ser.detail_dict(), msg=LOG_ISO_ATTACH)
        self._remove_dc_binding(res)

        return res

    def delete(self):
        ser = self.serializer(self.request, self.iso)
        self.iso.dc.remove(self.request.dc)
        res = SuccessTaskResponse(self.request, None, obj=self.iso, detail_dict=ser.detail_dict(), msg=LOG_ISO_DETACH)
        self._remove_dc_binding(res)

        return res
