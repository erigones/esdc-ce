from logging import getLogger

from django.utils.translation import ugettext_lazy as _

from api.status import HTTP_201_CREATED
from api.api_views import APIView
from api.exceptions import ExpectationFailed, InvalidInput
from api.utils.views import call_api_view
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.dns.domain.utils import get_domain, get_domains
from api.dns.domain.serializers import DomainSerializer, ExtendedDomainSerializer, TsigKeySerializer
from api.dns.messages import LOG_DOMAIN_CREATE, LOG_DOMAIN_UPDATE, LOG_DOMAIN_DELETE
from api.dc.utils import attach_dc_virt_object
from api.dc.messages import LOG_DOMAIN_ATTACH
from pdns.models import Record, TsigKey
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
                    if self.extended:
                        # add tsig_keys parameter from different model
                        res.update({'tsig_keys': [key.to_str() for key in TsigKey.get_linked_axfr_keys(self.domain)]})
                else:
                    res = []
            else:
                res = list(self.domain.values_list('name', flat=True))
        else:
            res = self.ser_class(self.request, self.domain).data
            if self.extended:
                res.update({'tsig_keys': [key.to_str() for key in TsigKey.get_linked_axfr_keys(self.domain)]})

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

        tsig_data = {}
        # in case there will be more tsig_* parameters (but for now, there's only tsig_keys)
        for key, val in self.data.items():
            # remove tsig_* parameters from request data because they belong to other validator
            if key.startswith('tsig_'):
                self.data.pop(key)
                tsig_data[key[5:]] = val    # e.g: tsig_keys -> keys

        tsig_keys_new, tsig_serializers = self.process_tsig_keys(request, tsig_data)

        # save default serializer
        ser.object.save()
        # save tsig serializer(s)
        [ser_tsig.object.save() for ser_tsig in tsig_serializers]
        # link newly defined TSIG keys to this domain
        [new_key.link_to_axfr_domain(domain) for new_key in tsig_keys_new]

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

        # validate the main Domain form before processing TSIG params
        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=domain, dc_bound=False)

        tsig_data = {}
        # in case there will be more tsig_* parameters (but for now, there's only tsig_keys)
        for key, val in self.data.items():
            # remove tsig_* parameters from request data because they belong to other validator
            if key.startswith('tsig_'):
                self.data.pop(key)
                tsig_data[key[5:]] = val    # e.g: tsig_keys -> keys

        tsig_keys_new, tsig_serializers = self.process_tsig_keys(request, tsig_data)

        # save default serializer
        ser.object.save()
        # save tsig serializer(s)
        [ser_tsig.object.save() for ser_tsig in tsig_serializers]
        # link newly defined TSIG keys to this domain
        [new_key.link_to_axfr_domain(domain) for new_key in tsig_keys_new]

        # unlink old TSIG keys that were defined for this domain but they were removed in this update
        tsig_keys_names = [key.name for key in tsig_keys_new]
        [linked_key.unlink_axfr_domain(domain) for linked_key in TsigKey.get_linked_axfr_keys(domain)
         if linked_key.name not in tsig_keys_names]

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

        # unlink TSIG keys that were defined for this domain
        [linked_key.unlink_axfr_domain(domain) for linked_key in TsigKey.get_linked_axfr_keys(domain)]

        domain.delete()

        return SuccessTaskResponse(self.request, None, obj=obj, owner=owner, msg=LOG_DOMAIN_DELETE, dc_bound=False)

    def process_tsig_keys(self, request, tsig_data):
        """
        :param request:
        :param tsig_data: dict that contains 'keys' key with the str containing comma separated key definitions
                (for key definition see TsigKey.parse_tsig_string())
        :return:
            On success:
            arg1: new_keys - list of new keys that are not yet in database (link them to this domain on commit)
            arg2: tsig_serializers - list of verified but not saved serializer classes \
                    (call .save() over each on commit)
            On error:
            :raises InvalidInput()
        """

        # remove spaces, ignore empty values
        try:
            tsig_keys = tsig_data['keys'].replace(' ', '')
            tsig_keys = [x for x in tsig_keys.split(',') if x]
        except (KeyError, AttributeError):
            # no tsig keys found
            return [], []

        tsig_serializers = []
        tsig_keys_new = []
        for tsig_key_str in tsig_keys:
            tsig_key_new_tmp = TsigKey.parse_tsig_string(tsig_key_str)
            if not tsig_key_new_tmp:
                raise InvalidInput('Invalid TSIG key: "%s"' % tsig_key_str)

            tsig_key_from_db = TsigKey.objects.filter(name=tsig_key_new_tmp.name)
            if not tsig_key_from_db:
                # key is not in DB. Create it.
                tsig_key = tsig_key_new_tmp
            else:
                # Key(s) with such name is already present. Check if the signature is also the same.
                # We assume that only one key with such name can be present in DB.
                # If our assumption is wrong, PDNS would probably fail anyway.
                tsig_key_from_db = tsig_key_from_db[0]
                if tsig_key_from_db.secret != tsig_key_new_tmp.secret:
                    linked_domains = tsig_key_from_db.get_linked_axfr_domains()
                    if len(linked_domains) == 0:
                        # this is probably DB inconsistency... we have a key but it's not used anywhere
                        pass
                    elif len(linked_domains) == 1 and linked_domains[0].id == self.domain.id:
                        # only one domain has this TSIG key defined - the domain we're editing just now.
                        # Therefore it's safe to edit the key.
                        tsig_key_from_db.secret = tsig_key_new_tmp.secret
                        pass
                    else:
                        raise InvalidInput('TSIG key with the same name "%s" and different secret is already used '
                                           'for other domain. Please use other key name.' % tsig_key_new_tmp.name)

                elif tsig_key_from_db.algorithm != tsig_key_new_tmp.algorithm:
                    raise InvalidInput('TSIG key\'s "%s" algorithm ("%s") does not match the one already saved in '
                                       'database ("%s")' % (tsig_key_new_tmp.name,
                                                            tsig_key_new_tmp.algorithm,
                                                            tsig_key_from_db.algorithm))
                else:
                    # the key is the same, we don't need to save it again
                    tsig_keys_new += [tsig_key_from_db]     # but we need it in this list
                    continue

                tsig_key = tsig_key_from_db

            ser_tsig = TsigKeySerializer(request, tsig_key, read_only=False, many=False, data=tsig_data)
            if not ser_tsig.is_valid():
                return FailureTaskResponse(request, ser_tsig.errors, obj=self.domain, dc_bound=False)

            # custom validation
            tsig_key.validate()

            tsig_serializers += [ser_tsig]
            tsig_keys_new += [tsig_key]

        return tsig_keys_new, tsig_serializers
