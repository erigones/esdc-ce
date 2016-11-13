from django.utils.translation import ugettext_noop as _

from api import status
from api.api_views import APIView
from api.exceptions import PreconditionRequired, ObjectAlreadyExists
from api.task.response import SuccessTaskResponse
from api.utils.db import get_object
from api.dc.utils import remove_dc_binding_virt_object
from api.dc.image.serializers import ImageSerializer
from api.dc.messages import LOG_IMAGE_ATTACH, LOG_IMAGE_DETACH
from api.image.messages import LOG_IMAGE_UPDATE
from vms.models import Image


class DcImageView(APIView):
    serializer = ImageSerializer
    order_by_default = order_by_fields = ('name',)

    def __init__(self, request, name, data):
        super(DcImageView, self).__init__(request)
        self.data = data
        self.name = name

        if name:
            attrs = {'name': name}

            if request.method != 'POST':
                attrs['dc'] = request.dc

            self.img = get_object(request, Image, attrs, sr=('owner', 'dc_bound'), exists_ok=True, noexists_fail=True)
        else:
            self.img = Image.objects.select_related('owner', 'dc_bound').filter(dc=request.dc)\
                                                                        .exclude(access__in=Image.INVISIBLE)\
                                                                        .order_by(*self.order_by)

    def get(self, many=False):
        if many or not self.name:
            if self.full:
                if self.img:
                    res = self.serializer(self.request, self.img, many=True).data
                else:
                    res = []
            else:
                res = list(self.img.values_list('name', flat=True))
        else:
            res = self.serializer(self.request, self.img).data

        return SuccessTaskResponse(self.request, res)

    def _remove_dc_binding(self, res):
        if self.img.dc_bound:
            remove_dc_binding_virt_object(res.data.get('task_id'), LOG_IMAGE_UPDATE, self.img, user=self.request.user)

    def post(self):
        dc, img = self.request.dc, self.img

        if img.dc.filter(id=dc.id).exists():
            raise ObjectAlreadyExists(model=Image)

        ser = self.serializer(self.request, img)
        img.dc.add(dc)
        res = SuccessTaskResponse(self.request, ser.data, obj=img, status=status.HTTP_201_CREATED,
                                  detail_dict=ser.detail_dict(), msg=LOG_IMAGE_ATTACH)
        self._remove_dc_binding(res)

        return res

    def delete(self):
        dc, img = self.request.dc, self.img

        if img.is_used_by_vms(dc=dc):
            raise PreconditionRequired(_('Image is used by some VMs'))

        ser = self.serializer(self.request, img)
        img.dc.remove(dc)
        res = SuccessTaskResponse(self.request, None, obj=img, detail_dict=ser.detail_dict(), msg=LOG_IMAGE_DETACH)
        self._remove_dc_binding(res)

        return res
