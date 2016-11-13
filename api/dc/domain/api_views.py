from django.utils.translation import ugettext_noop as _
from django.db.models import Q

from api import status
from api.api_views import APIView
from api.exceptions import ObjectAlreadyExists, ExpectationFailed
from api.task.response import SuccessTaskResponse
from api.utils.db import get_object
from api.dc.utils import remove_dc_binding_virt_object
from api.dc.domain.serializers import DomainSerializer
from api.dc.messages import LOG_DOMAIN_ATTACH, LOG_DOMAIN_DETACH
from api.dns.domain.utils import prefetch_domain_owner
from api.dns.messages import LOG_DOMAIN_UPDATE
from vms.models import DomainDc
from pdns.models import Domain


class DcDomainView(APIView):
    serializer = DomainSerializer
    order_by_default = order_by_fields = ('name',)

    def __init__(self, request, name, data):
        super(DcDomainView, self).__init__(request)
        self.data = data
        self.name = name

        if name:
            where = None

            if request.method != 'POST':
                where = Q(id__in=list(request.dc.domaindc_set.values_list('domain_id', flat=True)))

            self.domain = get_object(request, Domain, {'name': name.lower()}, where=where,
                                     exists_ok=True, noexists_fail=True)

        else:
            dc_domain_ids = list(request.dc.domaindc_set.values_list('domain_id', flat=True))
            self.domain = Domain.objects.filter(id__in=dc_domain_ids).order_by(*self.order_by)

    def get(self, many=False):
        if many or not self.name:
            if self.full:
                domains = prefetch_domain_owner(self.domain)
                if domains:
                    res = self.serializer(self.request, domains, many=True).data
                else:
                    res = []
            else:
                res = list(self.domain.values_list('name', flat=True))
        else:
            res = self.serializer(self.request, self.domain).data

        return SuccessTaskResponse(self.request, res)

    def _remove_dc_binding(self, res):
        if self.domain.dc_bound:
            remove_dc_binding_virt_object(res.data.get('task_id'), LOG_DOMAIN_UPDATE, self.domain,
                                          user=self.request.user)

    def post(self):
        dc, domain = self.request.dc, self.domain

        if DomainDc.objects.filter(dc=dc, domain_id=domain.id).exists():
            raise ObjectAlreadyExists(model=Domain)

        ser = self.serializer(self.request, domain)
        DomainDc.objects.create(dc=dc, domain_id=domain.id)
        res = SuccessTaskResponse(self.request, ser.data, obj=domain, status=status.HTTP_201_CREATED,
                                  detail_dict=ser.detail_dict(), msg=LOG_DOMAIN_ATTACH)
        self._remove_dc_binding(res)

        return res

    def delete(self):
        dc, domain = self.request.dc, self.domain

        if dc.settings.VMS_VM_DOMAIN_DEFAULT == domain.name:
            raise ExpectationFailed(_('Default VM domain cannot be removed from datacenter'))

        ser = DomainSerializer(self.request, domain)
        DomainDc.objects.filter(dc=dc, domain_id=domain.id).delete()
        res = SuccessTaskResponse(self.request, None, obj=domain, detail_dict=ser.detail_dict(), msg=LOG_DOMAIN_DETACH)
        self._remove_dc_binding(res)

        return res
