from logging import getLogger

from django.utils.translation import ugettext_lazy as _

from api.status import HTTP_201_CREATED
from api.api_views import APIView
from api.exceptions import ExpectationFailed
from api.utils.views import call_api_view
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.dns.domain.utils import get_domain, get_domains
from api.dns.domain.serializers import DomainSerializer, ExtendedDomainSerializer
from api.dns.messages import LOG_DOMAIN_CREATE, LOG_DOMAIN_UPDATE, LOG_DOMAIN_DELETE
from api.dc.utils import attach_dc_virt_object
from api.dc.messages import LOG_DOMAIN_ATTACH
from pdns.models import Domain, Record
from vms.models import Dc, DefaultDc

logger = getLogger(__name__)


class DomainView(APIView):
    dc_bound = False
    order_by_default = order_by_fields = ('name',)
    order_by_field_map = {'created': 'id'}

    def __init__(self, request, name, data):
        super(DomainView, self).__init__(request)
        self.data = data
        self.name = name

        if self.extended:
            self.ser_class = ExtendedDomainSerializer
        else:
            self.ser_class = DomainSerializer

        if name:
            self.domain = get_domain(request, name, fetch_dc=self.extended, data=data, count_records=self.extended)
        else:  # many
            self.domain = get_domains(request, prefetch_owner=self.full or self.extended, prefetch_dc=self.extended,
                                      count_records=self.extended, order_by=self.order_by)

    def get(self, many=False):
        if many or not self.name:
            if self.full or self.extended:
                if self.domain:
                    res = self.ser_class(self.request, self.domain, many=True).data
                else:
                    res = []
            else:
                res = list(self.domain.values_list('name', flat=True))
        else:
            res = self.ser_class(self.request, self.domain).data

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    def post(self):
        request = self.request
        dc1_settings = DefaultDc().settings
        domain = self.domain
        domain.owner = request.user  # just a default
        domain.type = dc1_settings.DNS_DOMAIN_TYPE_DEFAULT

        if not request.user.is_staff:
            self.data.pop('dc_bound', None)  # default DC binding cannot be changed when creating object

        ser = DomainSerializer(request, domain, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=domain, dc_bound=False)

        ser.object.save()
        res = SuccessTaskResponse(request, ser.data, status=HTTP_201_CREATED, obj=domain, dc_bound=False,
                                  msg=LOG_DOMAIN_CREATE, detail_dict=ser.detail_dict())

        # Create SOA and NS records for new MASTER/NATIVE domain
        from api.dns.record.views import dns_record
        try:
            if dc1_settings.DNS_SOA_DEFAULT and dc1_settings.DNS_NAMESERVERS:
                soa_attrs = {'hostmaster': dc1_settings.DNS_HOSTMASTER.replace('@', '.'),
                             'nameserver': dc1_settings.DNS_NAMESERVERS[0]}
                soa_data = {'type': Record.SOA, 'name': domain.name,
                            'content': dc1_settings.DNS_SOA_DEFAULT.format(**soa_attrs)}
                call_api_view(request, 'POST', dns_record, domain.name, 0, data=soa_data, log_response=True)

            for ns in dc1_settings.DNS_NAMESERVERS:
                ns_data = {'type': Record.NS, 'name': domain.name, 'content': ns}
                call_api_view(request, 'POST', dns_record, domain.name, 0, data=ns_data, log_response=True)
        except Exception as e:
            logger.exception(e)

        if domain.dc_bound:
            assert request.dc.id == domain.dc_bound
            attach_dc_virt_object(res.data.get('task_id'), LOG_DOMAIN_ATTACH, domain, request.dc,
                                  user=request.user)

        return res

    def put(self):
        request = self.request
        domain = self.domain
        ser = DomainSerializer(request, domain, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=domain, dc_bound=False)

        ser.object.save()
        res = SuccessTaskResponse(request, ser.data, obj=domain, msg=LOG_DOMAIN_UPDATE, detail_dict=ser.detail_dict(),
                                  dc_bound=False)

        if ser.name_changed:
            # Update SOA and NS records when MASTER/NATIVE Domain name changed
            from api.dns.record.views import dns_record
            try:
                data = {'name': domain.name}
                for record_id in domain.record_set.filter(name__iexact=ser.name_changed,
                                                          type__in=[Record.NS, Record.SOA])\
                                                  .values_list('id', flat=True):
                    call_api_view(request, 'PUT', dns_record, domain.name, record_id, data=data, log_response=True)
            except Exception as e:
                logger.exception(e)

            # Update VMS_VM_DOMAIN_DEFAULT if this domain was used as a default DC domain
            from api.dc.base.views import dc_settings
            try:
                for dc in Dc.objects.all():
                    if dc.settings.VMS_VM_DOMAIN_DEFAULT == ser.name_changed:
                        call_api_view(request, 'PUT', dc_settings, dc.name, data={'VMS_VM_DOMAIN_DEFAULT': domain.name},
                                      log_response=True)
            except Exception as e:
                logger.exception(e)

        return res

    def delete(self):
        domain = self.domain

        for dc in Dc.objects.all():
            if dc.settings.VMS_VM_DOMAIN_DEFAULT == domain.name:
                raise ExpectationFailed(_('Default VM domain cannot be deleted'))

        owner = domain.owner
        obj = domain.log_list
        domain.delete()

        return SuccessTaskResponse(self.request, None, obj=obj, owner=owner, msg=LOG_DOMAIN_DELETE, dc_bound=False)
