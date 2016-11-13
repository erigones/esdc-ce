import re

from django.conf import settings

from api.status import HTTP_201_CREATED
from api.api_views import APIView
from api.exceptions import PermissionDenied
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.utils.db import get_virt_object
from api.iso.base.serializers import IsoSerializer, ExtendedIsoSerializer
from api.iso.messages import LOG_ISO_CREATE, LOG_ISO_UPDATE, LOG_ISO_DELETE
from api.dc.utils import attach_dc_virt_object
from api.dc.messages import LOG_ISO_ATTACH
from vms.models import Iso


class IsoView(APIView):
    dc_bound = False
    order_by_default = order_by_fields = ('name',)
    order_by_field_map = {'created': 'id'}

    def __init__(self, request, name, data):
        super(IsoView, self).__init__(request)
        self.data = data
        self.name = name

        if self.extended:
            pr = ('dc',)
            self.ser_class = ExtendedIsoSerializer
        else:
            pr = ()
            self.ser_class = IsoSerializer

        self.iso = get_virt_object(request, Iso, data=data, pr=pr, many=not name, name=name, order_by=self.order_by)

    def get(self, many=False):
        if many or not self.name:
            if self.full or self.extended:
                if self.iso:
                    res = self.ser_class(self.request, self.iso, many=True).data
                else:
                    res = []
            else:
                res = list(self.iso.values_list('name', flat=True))
        else:
            res = self.ser_class(self.request, self.iso).data

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    def post(self):
        iso, request = self.iso, self.request

        if not request.user.is_staff:
            self.data.pop('dc_bound', None)  # default DC binding cannot be changed when creating object

        iso.owner = request.user  # just a default
        iso.alias = re.sub(r'\.iso\s*$', '', iso.name)  # just a default
        iso.status = Iso.OK  # TODO: status is not used right now
        ser = IsoSerializer(request, iso, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=iso, dc_bound=False)

        ser.object.save()
        res = SuccessTaskResponse(request, ser.data, status=HTTP_201_CREATED, obj=iso, dc_bound=False,
                                  detail_dict=ser.detail_dict(), msg=LOG_ISO_CREATE)

        if iso.dc_bound:
            attach_dc_virt_object(res.data.get('task_id'), LOG_ISO_ATTACH, iso, iso.dc_bound, user=request.user)

        return res

    def put(self):
        iso = self.iso
        ser = IsoSerializer(self.request, iso, data=self.data, partial=True)

        if iso.name == settings.VMS_ISO_RESCUECD:
            raise PermissionDenied

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=iso, dc_bound=False)

        ser.object.save()

        return SuccessTaskResponse(self.request, ser.data, obj=iso, detail_dict=ser.detail_dict(), msg=LOG_ISO_UPDATE,
                                   dc_bound=False)

    def delete(self):
        iso = self.iso
        ser = IsoSerializer(self.request, iso)

        if iso.name == settings.VMS_ISO_RESCUECD:
            raise PermissionDenied

        owner = iso.owner
        obj = iso.log_list
        ser.object.delete()

        return SuccessTaskResponse(self.request, None, obj=obj, owner=owner, msg=LOG_ISO_DELETE, dc_bound=False)
