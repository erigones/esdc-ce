from django.utils.translation import ugettext_noop as _

from api import status
from api.api_views import APIView
from api.exceptions import PreconditionRequired, ObjectAlreadyExists
from api.task.response import SuccessTaskResponse
from api.utils.db import get_object
from api.dc.utils import remove_dc_binding_virt_object
from api.dc.network.serializers import NetworkSerializer
from api.dc.messages import LOG_NETWORK_ATTACH, LOG_NETWORK_DETACH
from api.network.messages import LOG_NET_UPDATE
from vms.models import Subnet


class DcNetworkView(APIView):
    serializer = NetworkSerializer
    order_by_default = order_by_fields = ('name',)

    def __init__(self, request, name, data):
        super(DcNetworkView, self).__init__(request)
        self.data = data
        self.name = name

        if name:
            attrs = {'name': name}

            if request.method != 'POST':
                attrs['dc'] = request.dc

            self.net = get_object(request, Subnet, attrs, sr=('owner', 'dc_bound'), exists_ok=True, noexists_fail=True)
        else:
            self.net = Subnet.objects.select_related('owner', 'dc_bound').filter(dc=request.dc)\
                                                                         .exclude(access__in=Subnet.INVISIBLE)\
                                                                         .order_by(*self.order_by)

    def get(self, many=False):
        if many or not self.name:
            if self.full:
                if self.net:
                    res = self.serializer(self.request, self.net, many=True).data
                else:
                    res = []
            else:
                res = list(self.net.values_list('name', flat=True))
        else:
            res = self.serializer(self.request, self.net).data

        return SuccessTaskResponse(self.request, res)

    def _remove_dc_binding(self, res):
        if self.net.dc_bound:
            remove_dc_binding_virt_object(res.data.get('task_id'), LOG_NET_UPDATE, self.net, user=self.request.user)

    def post(self):
        dc, net = self.request.dc, self.net

        if net.dc.filter(id=dc.id).exists():
            raise ObjectAlreadyExists(model=Subnet)

        ser = NetworkSerializer(self.request, net)
        net.dc.add(dc)
        res = SuccessTaskResponse(self.request, ser.data, obj=net, status=status.HTTP_201_CREATED,
                                  detail_dict=ser.detail_dict(), msg=LOG_NETWORK_ATTACH)
        self._remove_dc_binding(res)

        return res

    def delete(self):
        dc, net = self.request.dc, self.net

        if net.is_used_by_vms(dc=dc):
            raise PreconditionRequired(_('Network is used by some VMs'))

        ser = NetworkSerializer(self.request, net)
        net.dc.remove(dc)
        res = SuccessTaskResponse(self.request, None, obj=net, detail_dict=ser.detail_dict(), msg=LOG_NETWORK_DETACH)
        self._remove_dc_binding(res)

        return res
