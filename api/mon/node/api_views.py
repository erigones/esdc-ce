from api.api_views import APIView
from api.exceptions import NodeIsNotOperational
from api.task.response import mgmt_task_response
from api.node.utils import get_node
from api.mon.node.tasks import mon_node_sla as t_mon_node_sla
from api.mon.node.utils import parse_yyyymm
from que import TG_DC_UNBOUND


class NodeSLAView(APIView):
    dc_bound = False

    def __init__(self, request, hostname, yyyymm, data):
        super(NodeSLAView, self).__init__(request)
        self.node = get_node(request, hostname)
        self.yyyymm = yyyymm
        self.data = data

    def get(self):
        request, node = self.request, self.node

        if node.status not in node.STATUS_OPERATIONAL:
            raise NodeIsNotOperational

        yyyymm, since, until, current_month = parse_yyyymm(self.yyyymm, node.created.replace(tzinfo=None))

        _apiview_ = {'view': 'mon_node_sla', 'method': request.method, 'hostname': node.hostname, 'yyyymm': yyyymm}

        _since = int(since.strftime('%s'))
        _until = int(until.strftime('%s')) - 1
        tidlock = 'mon_node_sla node:%s yyyymm:%s' % (node.uuid, yyyymm)

        if current_month:
            cache_timeout = 300
        else:
            cache_timeout = 86400

        ter = t_mon_node_sla.call(request, node.owner.id, (node.hostname, yyyymm, _since, _until),
                                  kwargs={'node_uuid': node.uuid}, meta={'apiview': _apiview_}, tg=TG_DC_UNBOUND,
                                  tidlock=tidlock, cache_result=tidlock, cache_timeout=cache_timeout)

        return mgmt_task_response(request, *ter, obj=node, api_view=_apiview_, dc_bound=False, data=self.data)


class NodeHistoryView(APIView):
    raise NotImplemented
