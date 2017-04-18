from api.api_views import APIView
from api.mon.base.tasks import mon_template_list as t_mon_template_list
from api.task.response import mgmt_task_response
from que import TG_DC_BOUND


class MonTemplateView(APIView):
    dc_bound = True

    def __init__(self, request, data):
        super(MonTemplateView, self).__init__(request)
        self.request = request
        self.data = data

    def get(self):
        request = self.request
        _apiview_ = {'view': 'mon_template_list', 'method': request.method}
        tidlock = 'mon_template_list:%s' % request.dc.id

        ter = t_mon_template_list.call(request, None, (request.dc.id, ),
                                       meta={'apiview': _apiview_}, tg=TG_DC_BOUND,
                                       tidlock=tidlock, cache_result=tidlock, cache_timeout=300)

        return mgmt_task_response(request, *ter, obj=request.dc,
                                  api_view=_apiview_, dc_bound=self.dc_bound, data=self.data)
