from logging import getLogger

from django.http import Http404

from api.api_views import APIView
# noinspection PyProtectedMember
from api.fields import get_boolean_value
from api.exceptions import PermissionDenied
from api.task.response import FailureTaskResponse, mgmt_task_response
from api.mon import MonitoringServer
from api.mon.messages import LOG_MON_HOSTGROUP_CREATE, LOG_MON_HOSTGROUP_DELETE
from api.mon.base.serializers import HostgroupSerializer
from api.mon.base.tasks import (mon_template_list, mon_hostgroup_list, mon_hostgroup_get, mon_hostgroup_create,
                                mon_hostgroup_delete)
from que import TG_DC_BOUND, TG_DC_UNBOUND
from vms.models import DefaultDc

logger = getLogger(__name__)


class MonBaseView(APIView):
    """
    Base class for MonTemplateView and MonHostgroupView, which are simple GET-only views.
    """
    _apiview_ = None
    _mon_server_ = None

    api_object_identifier = NotImplemented
    api_view_name_list = NotImplemented
    api_view_name_manage = NotImplemented
    mgmt_task_list = NotImplemented

    def __init__(self, request, name, data, dc_bound=True):
        super(MonBaseView, self).__init__(request)
        self.name = name
        self.data = data
        self.dc_bound = dc_bound

    def _create_apiview(self):
        if self.name:
            return {
                'view': self.api_view_name_manage,
                'method': self.request.method,
                self.api_object_identifier: self.name,
            }
        else:
            return {
                'view': self.api_view_name_list,
                'method': self.request.method
            }

    @property
    def _apiview(self):
        if self._apiview_ is None:
            self._apiview_ = self._create_apiview()
        return self._apiview_

    @property
    def _mon_server(self):
        if self._mon_server_ is None:
            self._mon_server_ = MonitoringServer(self.request.dc)
        return self._mon_server_

    def _create_task(self, task, msg=None, tidlock=None, cache_result=None, cache_timeout=None, task_kwargs=None):
        if self.name:
            args = (self.request.dc.id, self.name)
        else:
            args = (self.request.dc.id,)

        # Add information for emergency task cleanup - see api.task.utils.mgmt_task decorator
        kwargs = {'mon_server_id': self._mon_server.id, 'dc_bound': self.dc_bound}

        if task_kwargs:
            kwargs.update(task_kwargs)

        # Add apiview information for task log purposes inside tasks
        meta = {'apiview': self._apiview}

        if msg:
            meta['msg'] = msg

        # WARNING: This will change the the task group.
        # Please make sure that your request.dc is set to DefaultDC for dc_unbound tasks.
        if self.dc_bound:
            tg = TG_DC_BOUND
        else:
            tg = TG_DC_UNBOUND

        return task.call(self.request, None, args, kwargs=kwargs, meta=meta, tg=tg, tidlock=tidlock,
                         cache_result=cache_result, cache_timeout=cache_timeout)

    def _create_task_and_response(self, task, msg=None, detail_dict=None, tidlock=None, cache_result=None,
                                  cache_timeout=None, task_kwargs=None):
        tid, err, res = self._create_task(task, msg=msg, tidlock=tidlock, cache_result=cache_result,
                                          cache_timeout=cache_timeout, task_kwargs=task_kwargs)

        # Do not log on error
        if err:
            obj, msg = None, None
        else:
            obj = self._mon_server

        return mgmt_task_response(self.request, tid, err, res, msg=msg, obj=obj, api_view=self._apiview,
                                  detail_dict=detail_dict)

    @classmethod
    def generate_cache_key_base(cls, dc_name, dc_bound, full=False, extended=False):
        return '%s:%s:%s:full=%s:extended=%s' % (cls.api_view_name_list, dc_name, dc_bound, full, extended)

    @classmethod
    def clear_cache(cls, dc_name, dc_bound, full=False, extended=False):
        return cls.mgmt_task_list.clear_cache(cls.generate_cache_key_base(dc_name, dc_bound, full=full,
                                                                          extended=extended))

    def get_list(self, task, cache=False, cache_timeout=None):
        task_kwargs = {'full': self.full, 'extended': self.extended}

        if cache:
            tidlock = self.generate_cache_key_base(self.request.dc.name, self.dc_bound, full=self.full,
                                                   extended=self.extended)
        else:
            tidlock = None

        return self._create_task_and_response(task, tidlock=tidlock, cache_result=tidlock,
                                              cache_timeout=cache_timeout, task_kwargs=task_kwargs)


class MonTemplateView(MonBaseView):
    api_view_name_list = 'mon_template_list'
    mgmt_task_list = mon_template_list

    def get(self, many=False):
        if many:
            return self.get_list(mon_template_list, cache=True, cache_timeout=30)
        else:
            raise NotImplementedError


class MonHostgroupView(MonBaseView):
    api_object_identifier = 'hostgroup_name'
    api_view_name_list = 'mon_hostgroup_list'
    api_view_name_manage = 'mon_hostgroup_manage'
    mgmt_task_list = mon_hostgroup_list

    @staticmethod
    def is_dc_bound(data, default=True):
        if bool(data):
            return get_boolean_value(data.get('dc_bound', default))
        else:
            return default

    @staticmethod
    def switch_dc_to_default(request):
        if not request.dc.is_default():
            request.dc = DefaultDc()  # Warning: Changing request.dc
            logger.info('"%s %s" user="%s" _changed_ dc="%s" permissions=%s', request.method, request.path,
                        request.user.username, request.dc.name, request.dc_user_permissions)

            if not request.dc.settings.MON_ZABBIX_ENABLED:  # dc1_settings
                raise Http404

    @classmethod
    def get_dc_bound(cls, request, data):
        dc_bound = cls.is_dc_bound(data)

        if not dc_bound:
            if not request.user.is_staff:
                raise PermissionDenied

            cls.switch_dc_to_default(request)

        return dc_bound

    def get(self, many=False):
        if many:
            return self.get_list(mon_hostgroup_list, cache=True, cache_timeout=30)
        else:
            return self._create_task_and_response(mon_hostgroup_get)

    def post(self):
        self.data['name'] = self.name
        ser = HostgroupSerializer(self.request, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors)

        # noinspection PyStatementEffect
        ser.data

        return self._create_task_and_response(mon_hostgroup_create, msg=LOG_MON_HOSTGROUP_CREATE,
                                              detail_dict=ser.detail_dict(force_full=True))

    def delete(self):
        return self._create_task_and_response(mon_hostgroup_delete, msg=LOG_MON_HOSTGROUP_DELETE,
                                              detail_dict={'name': self.name})
