from django.db.models import Q
from django.db.transaction import atomic
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError

from api.status import HTTP_201_CREATED
from api.api_views import APIView
from api.exceptions import ObjectNotFound, ObjectAlreadyExists, PreconditionRequired, InvalidInput
from api.fields import cidr_validator
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.utils.db import get_object, get_virt_object
from api.network.ip.serializers import NetworkIPSerializer, NetworkIPPlanSerializer
from api.network.messages import LOG_IP_CREATE, LOG_IP_UPDATE, LOG_IP_DELETE, LOG_IPS_CREATE, LOG_IPS_DELETE
from vms.models import IPAddress, Subnet


class NetworkIPView(APIView):
    dc_bound = False
    order_by_default = ('id',)
    order_by_fields = ('ip',)
    order_by_field_map = {'hostname': 'vm__hostname'}

    def __init__(self, request, name, ip, data, dc=None, many=False):
        super(NetworkIPView, self).__init__(request)
        self.data = data
        self.many = many
        self.dc = dc
        net_filter = {'name': name}
        ip_filter = {}
        ip_exclude = {}
        where = None

        if dc:
            net_filter['dc'] = dc
            ip_filter['usage__in'] = [IPAddress.VM, IPAddress.VM_REAL]
            ip_filter['vm__dc'] = dc
            ip_filter['vm__isnull'] = False
        elif not request.user.is_staff:
            if many:
                ip_exclude['usage'] = IPAddress.NODE
            else:
                where = ~Q(usage=IPAddress.NODE)

        self.net = net = get_virt_object(request, Subnet, data=data, sr=('dc_bound',), get_attrs=net_filter,
                                         exists_ok=True, noexists_fail=True)
        ip_filter['subnet'] = net

        if many:
            self.ips = ips = data.get('ips', None)

            if ips is not None:
                if not isinstance(ips, (tuple, list)):
                    raise InvalidInput('Invalid ips')
                ip_filter['ip__in'] = ips

            if request.method == 'GET':
                usage = data.get('usage', None)

                if usage and not dc:
                    try:
                        usage = int(usage)
                        if usage not in dict(IPAddress.USAGE_REAL):
                            raise ValueError
                    except ValueError:
                        raise InvalidInput('Invalid usage')
                    else:
                        ip_filter['usage'] = usage

            try:
                self.ip = IPAddress.objects.select_related('vm', 'vm__dc', 'subnet')\
                                           .exclude(**ip_exclude)\
                                           .filter(**ip_filter)\
                                           .order_by(*self.order_by)
            except TypeError:
                raise InvalidInput('Invalid ips')

        else:
            ip_filter['ip'] = ip
            self.ip = get_object(request, IPAddress, ip_filter, where=where, sr=('vm', 'vm__dc', 'subnet'))

    def get(self):
        if self.many:
            if self.full:
                if self.ip:
                    res = NetworkIPSerializer(self.net, self.ip, many=True).data
                else:
                    res = []
            else:
                res = list(self.ip.values_list('ip', flat=True))
        else:
            res = NetworkIPSerializer(self.net, self.ip).data

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    @atomic
    def post(self):
        dd = {}

        if 'note' in self.data:
            dd['note'] = note = self.data['note']
        else:
            note = ''

        if 'usage' in self.data:
            dd['usage'] = usage = self.data['usage']
        else:
            usage = IPAddress.VM

        if self.many:
            ips = self.ips

            if not ips:
                raise InvalidInput('Invalid ips')

            if self.ip.exists():  # SELECT count(*) from IPAddress
                raise ObjectAlreadyExists(model=IPAddress)

            msg = LOG_IPS_CREATE
            data = [{'ip': ip, 'usage': usage, 'note': note} for ip in ips]
            dd['ips'] = '%s-%s' % (ips[0], ips[-1])

        else:
            msg = LOG_IP_CREATE
            data = dd
            data['ip'] = self.ip.ip

        ser = NetworkIPSerializer(self.net, data=data, many=self.many)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, dc_bound=False)

        if self.many:
            IPAddress.objects.bulk_create(ser.object)  # INSERT into IPAddress
        else:
            ser.object.save()  # INSERT into IPAddress

        return SuccessTaskResponse(self.request, ser.data, status=HTTP_201_CREATED, obj=self.net, msg=msg,
                                   detail_dict=dd, dc_bound=False)

    def put(self):
        data = {'ip': self.ip.ip}

        if 'note' in self.data:
            data['note'] = self.data['note']
        if 'usage' in self.data:
            data['usage'] = self.data['usage']

        ser = NetworkIPSerializer(self.net, self.ip, data=data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, dc_bound=False)

        ser.object.save()

        return SuccessTaskResponse(self.request, ser.data, obj=self.net, msg=LOG_IP_UPDATE, dc_bound=False,
                                   detail_dict=data)

    @atomic
    def delete(self):
        ip = self.ip

        if self.many:
            if not ip:  # SELECT count(*) from IPAddress ???
                raise ObjectNotFound(model=IPAddress)
            for i in ip:  # SELECT * from IPAddress
                if i.vm:
                    raise PreconditionRequired(_('IP address "%s" is used by VM') % i.ip)
                if i.is_node_address():
                    raise PreconditionRequired(_('IP address "%s" is used by Compute node') % i.ip)

            msg = LOG_IPS_DELETE
            dd = {'ips': ','.join(i.ip for i in ip)}

        else:
            if ip.vm:
                raise PreconditionRequired(_('IP address is used by VM'))
            if ip.is_node_address():
                raise PreconditionRequired(_('IP address is used by Compute node'))

            msg = LOG_IP_DELETE
            dd = {'ip': ip.ip}

        ip.delete()  # DELETE from IPAddress

        return SuccessTaskResponse(self.request, None, obj=self.net, msg=msg, detail_dict=dd, dc_bound=False)


class NetworkIPPlanView(APIView):
    """
    Display all IPs according to subnet (network/netmask).
    """
    dc_bound = False
    order_by_default = ('ip',)
    order_by_fields = ('ip',)
    order_by_field_map = {'net': 'subnet__name', 'hostname': 'vm__hostname'}

    def __init__(self, request, subnet, data, dc=None):
        super(NetworkIPPlanView, self).__init__(request)
        self.data = data
        self.dc = dc
        ip_filter = {}

        if subnet:
            try:
                ipi = cidr_validator(subnet, return_ip_interface=True)
            except ValidationError:
                raise InvalidInput('Invalid subnet')

            network, netmask = ipi.with_netmask.split('/')
            net_filter = {'network': network, 'netmask': netmask}

            if dc:
                net_filter['dc'] = dc

            nets = Subnet.objects.filter(**net_filter)

            if not nets.exists():
                raise ObjectNotFound(model=Subnet)

            ip_filter['subnet__in'] = nets

        if dc:
            ip_filter['usage'] = IPAddress.VM
            ip_filter['vm__dc'] = dc
            ip_filter['vm__isnull'] = False

        usage = data.get('usage', None)
        if usage and not dc:
            try:
                usage = int(usage)
                if usage not in dict(IPAddress.USAGE_REAL):
                    raise ValueError
            except ValueError:
                raise InvalidInput('Invalid usage')
            else:
                ip_filter['usage'] = usage

        self.ips = IPAddress.objects.select_related('vm', 'vm__dc', 'subnet').filter(**ip_filter)\
                                                                             .order_by(*self.order_by)

    def get(self):
        if self.full:
            if self.ips:
                res = NetworkIPPlanSerializer(None, self.ips, many=True).data
            else:
                res = []
        else:
            res = list(self.ips.values_list('ip', flat=True))

        return SuccessTaskResponse(self.request, res, dc_bound=False)
