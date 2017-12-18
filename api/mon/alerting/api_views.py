from logging import getLogger
from django.http import Http404

from api.api_views import APIView
from api.task.response import to_string, mgmt_task_response, FailureTaskResponse
from api.mon.alerting.serializers import AlertSerializer
from api.mon.alerting.tasks import mon_alert_list
from vms.models import DefaultDc
from que import TG_DC_BOUND, TG_DC_UNBOUND

logger = getLogger(__name__)


class MonAlertView(APIView):
    cache_timeout = 30

    def get(self):
        request = self.request
        ser = AlertSerializer(request, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors)

        dc_bound = ser.data['dc_bound']

        if dc_bound:
            tg = TG_DC_BOUND
        else:
            tg = TG_DC_UNBOUND

            if not request.dc.is_default():
                request.dc = DefaultDc()  # Warning: Changing request.dc
                logger.info('"%s %s" user="%s" _changed_ dc="%s" permissions=%s', request.method, request.path,
                            request.user.username, request.dc.name, request.dc_user_permissions)

                if not request.dc.settings.MON_ZABBIX_ENABLED:  # dc1_settings
                    raise Http404

        _apiview_ = {
            'view': 'mon_alert_list',
            'method': request.method
        }
        _tidlock = [
            'mon_alert_list',
            'dc_id=%s' % request.dc.id,
            'vm_uuids=%s' % ','.join(ser.vms or ()),
            'node_uuids=%s' % ','.join(ser.nodes or ()),
        ]
        task_kwargs = {
            'vm_uuids': ser.vms,
            'node_uuids': ser.nodes,
        }

        for key, val in ser.data.items():
            _apiview_[key] = val
            if not (key.startswith('vm_') or key.startswith('node_')):
                task_kwargs[key] = val
                _tidlock.append('%s=%s' % (key, to_string(val)))

        tidlock = ':'.join(_tidlock)
        ter = mon_alert_list.call(request, None, (request.dc.id,), kwargs=task_kwargs, meta={'apiview': _apiview_},
                                  tg=tg, tidlock=tidlock, cache_result=tidlock, cache_timeout=self.cache_timeout)

        return mgmt_task_response(request, *ter, obj=request.dc, api_view=_apiview_, dc_bound=dc_bound,
                                  data=self.data, detail_dict=ser.detail_dict(force_full=True))
