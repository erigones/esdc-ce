from api.api_views import APIView
from api.mon.base.tasks import mon_template_list, mon_hostgroup_list
from api.task.response import mgmt_task_response
from que import TG_DC_BOUND, TG_DC_UNBOUND


class _MonBaseView(APIView):
    api_view_name = NotImplemented
    mgmt_task = NotImplemented

    def __init__(self, request, data, dc_bound=True):
        super(_MonBaseView, self).__init__(request)
        self.request = request
        self.data = data
        self.dc_bound = dc_bound

    def get(self):
        request = self.request
        _apiview_ = {'view': self.api_view_name, 'method': request.method}
        tidlock = '%s:%s:%s' % (self.api_view_name, request.dc.id, self.dc_bound)

        if self.dc_bound:
            tg = TG_DC_BOUND
        else:
            tg = TG_DC_UNBOUND

        ter = self.mgmt_task.call(request, None,
                                  (request.dc.id,),
                                  meta={'apiview': _apiview_},
                                  tg=tg,
                                  tidlock=tidlock, cache_result=tidlock, cache_timeout=10)

        return mgmt_task_response(request, *ter, obj=request.dc, api_view=_apiview_, dc_bound=self.dc_bound,
                                  data=self.data)


class MonTemplateView(_MonBaseView):
    api_view_name = 'mon_template_list'
    mgmt_task = mon_template_list


class MonHostgroupView(_MonBaseView):
    api_view_name = 'mon_hostgroup_list'
    mgmt_task = mon_hostgroup_list
