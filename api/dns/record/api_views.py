from logging import getLogger

from django.utils.translation import ugettext_lazy as _

from api.status import HTTP_201_CREATED
from api.api_views import APIView
from api.utils.db import get_object
from api.utils.views import call_api_view
from api.decorators import catch_api_exception
from api.exceptions import ExpectationFailed, InvalidInput, ObjectNotFound
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.dns.domain.utils import get_domain
from api.dns.record.serializers import RecordSerializer
from api.dns.messages import LOG_RECORD_CREATE, LOG_RECORD_UPDATE, LOG_RECORD_DELETE, LOG_RECORDS_DELETE
from pdns.models import Domain, Record

logger = getLogger(__name__)


class RecordView(APIView):
    Domain = Domain
    Record = Record
    _log_failure = False
    dc_bound = False
    order_by_default = ('id',)
    order_by_fields = ('id', 'name', 'type', 'ttl', 'disabled', 'changed')
    order_by_field_map = {'changed': 'change_date'}

    def __init__(self, request, domain_name, record_id, data, record=None, task_id=None, related_obj=None):
        super(RecordView, self).__init__(request)
        self.domain_name = domain_name
        self.record_id = record_id
        self.data = data
        self.task_id = task_id
        self.related_obj = related_obj  # Added into detail dict for task log purposes

        if record:  # Shortcut used by VmDefineSerializer.save_ptr/save_a and NodeDefineView/node_sysinfo_cb
            self.record = record
            self.domain = record.domain
            self._log_failure = True
        else:
            self._set_record()

    def _set_record(self):
        request = self.request
        record_id = self.record_id

        # Check IsSuperAdmin or IsDomainOwner permissions in get_domain
        self.domain = get_domain(request, self.domain_name, exists_ok=True, noexists_fail=True)

        # Records for slave domains cannot be modified
        if request.method != 'GET' and self.domain.type in (Domain.SLAVE, Domain.SUPERSLAVE):
            raise ExpectationFailed(_('Changing DNS records is not allowed for %s domain') % self.domain.type)

        if record_id is None:  # Get many
            records = self.data.get('records', None)
            qs = self.domain.record_set.select_related('domain').order_by(*self.order_by)

            if records is None:
                self.record = qs
            else:
                if not isinstance(records, (tuple, list)):
                    raise InvalidInput('Invalid records')
                self.record = qs.filter(id__in=records)
        else:
            if record_id == 0:  # New record
                self.record = Record(domain=self.domain)
            else:  # Existing record
                self.record = get_object(request, Record, {'domain': self.domain, 'id': record_id}, sr=('domain',),
                                         noexists_fail=True)

    def _fix_detail_dict(self, dd):
        related_obj = self.related_obj

        if related_obj:
            # noinspection PyProtectedMember
            dd[related_obj._meta.verbose_name_raw.lower()] = related_obj.log_name

        return dd

    def log_failure(self, msg):
        if self._log_failure:
            return {
                'detail_dict': self._fix_detail_dict(self.data.copy()),
                'msg': msg,
            }
        else:
            return {}

    def get(self, many=False):
        if many or not self.record_id:
            if self.full:
                if self.record:
                    res = RecordSerializer(self.request, self.record, many=True).data
                else:
                    res = []
            else:
                res = list(self.record.values_list('id', flat=True))
        else:
            res = RecordSerializer(self.request, self.record).data

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    def post(self):
        ser = RecordSerializer(self.request, self.record, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=self.domain, dc_bound=False,
                                       task_id=self.task_id, **self.log_failure(LOG_RECORD_CREATE))

        ser.object.save()

        return SuccessTaskResponse(self.request, ser.data, status=HTTP_201_CREATED, obj=self.domain,
                                   detail_dict=self._fix_detail_dict(ser.detail_dict()), msg=LOG_RECORD_CREATE,
                                   task_id=self.task_id, dc_bound=False)

    def put(self):
        record = self.record
        ser = RecordSerializer(self.request, record, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=self.domain, dc_bound=False,
                                       task_id=self.task_id, **self.log_failure(LOG_RECORD_UPDATE))

        ser.object.save()

        return SuccessTaskResponse(self.request, ser.data, obj=self.domain, msg=LOG_RECORD_UPDATE, dc_bound=False,
                                   task_id=self.task_id, detail_dict=self._fix_detail_dict(ser.detail_dict()))

    def delete(self, many=False):
        record = self.record

        if many:
            assert not self.record_id

            if not record:  # SELECT count(*) from record ???
                raise ObjectNotFound(model=Record)

            msg = LOG_RECORDS_DELETE
            dd = {'records': [r.desc for r in record]}
        else:
            msg = LOG_RECORD_DELETE
            dd = {'record': record.desc}

        record.delete()

        return SuccessTaskResponse(self.request, None, obj=self.domain, msg=msg, detail_dict=self._fix_detail_dict(dd),
                                   task_id=self.task_id, dc_bound=False)

    @classmethod
    def internal_response(cls, request, method, record, data, task_id=None, related_obj=None):
        """Called by VmDefineSerializer"""
        return call_api_view(request, method, cls, record.domain.name, record.id, data=data, record=record,
                             task_id=task_id, related_obj=related_obj, api_class=True, log_response=True)

    @classmethod
    def internal_domain_get(cls, domain_name, task_id=None):
        """Used internally by some api functions"""
        try:
            return Domain.objects.get(name=domain_name)
        except Domain.DoesNotExist:
            raise ObjectNotFound(model=Domain, task_id=task_id)

    @classmethod
    @catch_api_exception
    def add_or_update_record(cls, request, record_type, domain_name, name, content, task_id=None, **kwargs):
        """Called internally by some api functions"""
        if not request.dc.settings.DNS_ENABLED:
            logger.info('DNS support disabled: skipping add_or_update_record(%r, %r, %r %r)',
                        record_type, domain_name, name, content)
            return None

        name = name.lower()  # DB constraint c_lowercase_name
        domain = cls.internal_domain_get(domain_name, task_id=task_id)

        try:
            record = Record.objects.get(type=record_type, name=name, domain=domain)
        except Record.DoesNotExist:
            logger.info('Adding %s record "%s" with content "%s" on domain "%s"', record_type, name, content, domain)
            record = Record(domain=domain)
            method = 'POST'
            data = {'type': record_type, 'domain': domain_name, 'name': name, 'content': content}
        else:
            logger.info('Updating %s record "%s" with content "%s" on domain "%s"', record_type, name, content, domain)
            method = 'PUT'
            data = {'content': content}

        return cls.internal_response(request, method, record, data, task_id=task_id, **kwargs)

    @classmethod
    @catch_api_exception
    def delete_record(cls, request, record_type, domain_name, name, task_id=None, **kwargs):
        """Called internally by some api functions"""
        if not request.dc.settings.DNS_ENABLED:
            logger.info('DNS support disabled: skipping delete_record(%r, %r, %r)',
                        record_type, domain_name, name)
            return None

        name = name.lower()  # DB constraint c_lowercase_name
        domain = cls.internal_domain_get(domain_name, task_id=task_id)

        try:
            record = Record.objects.get(name=name, type=record_type, domain=domain)
        except Record.DoesNotExist:
            raise ObjectNotFound(model=Record)

        logger.info('Deleting %s record "%s" on domain "%s"', record_type, name, domain)

        return cls.internal_response(request, 'DELETE', record, {}, task_id=task_id, **kwargs)
