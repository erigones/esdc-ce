from api.mon.node.graphs import GRAPH_ITEMS
from api.api_views import APIView
from api.exceptions import NodeIsNotOperational, InvalidInput
from api.mon.node.tasks import mon_node_sla as t_mon_node_sla, mon_node_history as t_mon_node_history
from api.mon.node.utils import parse_yyyymm
from api.mon.node.serializers import MonNodeHistorySerializer
from api.node.utils import get_node
from api.task.response import mgmt_task_response, FailureTaskResponse
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
    """ """
    def __init__(self, request, hostname, graph_type, item_id, data):
        super(VMHistoryView, self).__init__(request)
        self.request = request
        self.node = get_node(request, hostname)
        self.graph_type = graph_type
        self.item_id = item_id
        self.data = data

    def get(self):
        request, node, graph, item_id = self.request, self.node, self.graph_type, self.item_id

        if node.status not in node.STATUS_OPERATIONAL:
            raise NodeIsNotOperational

        # for selected graphs validate item_id, otherwise set it to None
        if graph.startswith(('net-', 'disk-')):
            if item_id is None:
                raise InvalidInput('Missing item_id parameter in URI')
            try:
                item_id = int(item_id)
            except Exception as e:
                raise InvalidInput('Invalid input value for item_id, must be integer!')
        else:
            self.item_id = item_id = None

        try:
            graph_settings = GRAPH_ITEMS.get_options(graph, node)
        except KeyError:
            raise InvalidInput('Invalid graph')
        else:
            required_ostype = graph_settings.get('required_ostype', None)

            if required_ostype is not None and node.ostype not in required_ostype:
                raise InvalidInput('Invalid OS type')

        _apiview_ = {'view': 'mon_node_history',
                     'method': request.method,
                     'hostname': node.zabbix_name,
                     'graph': graph}

        ser = MonNodeHistorySerializer(data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=node)

        result = ser.object.copy()
        result['desc'] = graph_settings.get('desc', '')
        result['hostname'] = node.zabbix_name
        result['graph'] = graph
        result['options'] = graph_settings.get('options', {})
        result['update_interval'] = graph_settings.get('update_interval', None)
        tidlock = 'mon_node_history node:%s graph:%s since:%d until:%d' % (node.uuid, graph,
                                                                           round(ser.object['since'], -2),
                                                                           round(ser.object['until'], -2))

        if item_id is None:
            items = graph_settings['items']
        else:
            item_dict = {'id': item_id}
            items = [i % item_dict for i in graph_settings['items']]

        if 'items_search_fun' in graph_settings:
            # noinspection PyCallingNonCallable
            items_search = graph_settings['items_search_fun'](graph_settings, item_id)
        else:
            items_search = None

        history = graph_settings['history']
        ter = t_mon_node_history.call(request, node.owner.id, (node.uuid, items, history, result, items_search),
                                      meta={'apiview': _apiview_}, tidlock=tidlock)
        # NOTE: cache_result=tidlock, cache_timeout=60)
        # Caching is disable here, because it makes no real sense.
        # The latest graphs must be fetched from zabbix and the older are requested only seldom.

        return mgmt_task_response(request, *ter, obj=node, api_view=_apiview_, data=self.data)
