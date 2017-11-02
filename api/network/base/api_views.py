from django.utils.translation import ugettext_lazy as _

from api.status import HTTP_201_CREATED
from api.api_views import APIView
from api.exceptions import PreconditionRequired
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.utils.db import get_virt_object
from api.network.base.serializers import NetworkSerializer, ExtendedNetworkSerializer
from api.network.messages import LOG_NET_CREATE, LOG_NET_UPDATE, LOG_NET_DELETE
from api.dc.utils import attach_dc_virt_object
from api.dc.messages import LOG_NETWORK_ATTACH
from vms.models import Subnet


class NetworkView(APIView):
    dc_bound = False
    order_by_default = ('name',)
    order_by_fields = ('name', 'created')

    def __init__(self, request, name, data):
        super(NetworkView, self).__init__(request)
        self.data = data
        self.name = name

        if self.extended:
            pr = ('dc',)
            self.ser_class = ExtendedNetworkSerializer
            extra = {'select': ExtendedNetworkSerializer.extra_select}
        else:
            pr = ()
            self.ser_class = NetworkSerializer
            extra = None

        self.net = get_virt_object(request, Subnet, data=data, pr=pr, extra=extra, many=not name, name=name,
                                   order_by=self.order_by)

    def get(self, many=False):
        if many or not self.name:
            if self.full or self.extended:
                if self.net:
                    res = self.ser_class(self.request, self.net, many=True).data
                else:
                    res = []
            else:
                res = list(self.net.values_list('name', flat=True))
        else:
            res = self.ser_class(self.request, self.net).data

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    def post(self):
        net, request = self.net, self.request

        if not request.user.is_staff:
            self.data.pop('dc_bound', None)  # default DC binding cannot be changed when creating object

        net.owner = request.user  # just a default
        net.alias = net.name  # just a default
        ser = NetworkSerializer(request, net, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=net, dc_bound=False)

        ser.object.save()
        res = SuccessTaskResponse(request, ser.data, status=HTTP_201_CREATED, obj=net, dc_bound=False,
                                  detail_dict=ser.detail_dict(), msg=LOG_NET_CREATE)

        if net.dc_bound:
            attach_dc_virt_object(res.data.get('task_id'), LOG_NETWORK_ATTACH, net, net.dc_bound, user=request.user)

        return res

    def put(self):
        net, request = self.net, self.request
        ser = NetworkSerializer(request, net, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=net, dc_bound=False)

        data = ser.data
        dd = ser.detail_dict()
        # These fields cannot be updated when net is used by some VM
        updated_ro_fields = {i for i in ('network', 'netmask', 'gateway', 'nic_tag',
                                         'vlan_id', 'vxlan_id', 'mtu', 'dhcp_passthrough')
                             if i in dd}
        # These fields cannot be updated when IP addresses exist
        updated_ro_fields2 = updated_ro_fields.intersection(('network', 'netmask'))

        if updated_ro_fields2 and net.ipaddress_set.exists():
            err = ser.update_errors(updated_ro_fields, _('This field cannot be updated '
                                                         'because network has existing IP addresses.'))
            return FailureTaskResponse(request, err, obj=net, dc_bound=False)

        if updated_ro_fields and net.is_used_by_vms():
            err = ser.update_errors(updated_ro_fields, _('This field cannot be updated '
                                                         'because network is used by some VMs.'))
            return FailureTaskResponse(request, err, obj=net, dc_bound=False)

        ser.object.save()

        return SuccessTaskResponse(self.request, data, obj=net, detail_dict=dd, msg=LOG_NET_UPDATE, dc_bound=False)

    def delete(self):
        net = self.net
        ser = NetworkSerializer(self.request, net)

        if net.is_used_by_vms():
            raise PreconditionRequired(_('Network is used by some VMs'))

        owner = net.owner
        obj = net.log_list
        ser.object.delete()

        return SuccessTaskResponse(self.request, None, obj=obj, owner=owner, msg=LOG_NET_DELETE, dc_bound=False)
