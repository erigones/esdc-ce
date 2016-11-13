from django.db.transaction import atomic

from api.api_views import APIView
from api.exceptions import InvalidInput, VmIsNotOperational, VmIsLocked, ExpectationFailed
from api.task.response import mgmt_task_response, FailureTaskResponse, SuccessTaskResponse
from api.vm.utils import get_vm
from api.mon.messages import LOG_MONDEF_UPDATE
from api.mon.node.utils import parse_yyyymm
from api.mon.vm.tasks import mon_vm_sla as t_mon_vm_sla, mon_vm_history as t_mon_vm_history
from api.mon.vm.serializers import VmMonitoringSerializer, MonVmHistorySerializer
from api.mon.vm.graphs import GRAPH_ITEMS
from api.vm.define.utils import VM_STATUS_OPERATIONAL


class VmMonitoringView(APIView):
    """
    api.mon.vm.mon_vm_define
    """
    def __init__(self, request, hostname, data):
        super(VmMonitoringView, self).__init__(request)
        self.vm = get_vm(request, hostname, sr=('dc',))
        self.data = data

    def get(self, many=False):
        assert not many, 'Working with multiple objects is not supported'

        request, vm = self.request, self.vm

        if request.query_params.get('active', False):
            vm.revert_active(json_only=True)

        res = VmMonitoringSerializer(request, vm).data

        return SuccessTaskResponse(request, res, obj=vm)

    @atomic
    def put(self):
        request, vm = self.request, self.vm

        if vm.locked:
            raise VmIsLocked

        if vm.status not in VM_STATUS_OPERATIONAL:
            raise VmIsNotOperational

        ser = VmMonitoringSerializer(request, vm, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=vm)

        ser.object.save()

        return SuccessTaskResponse(request, ser.data, obj=vm, detail_dict=ser.detail_dict(), msg=LOG_MONDEF_UPDATE)


class VmSLAView(APIView):
    def __init__(self, request, hostname, yyyymm, data):
        super(VmSLAView, self).__init__(request)
        self.vm = get_vm(request, hostname, sr=())
        self.yyyymm = yyyymm
        self.data = data

    def get(self):
        request, vm = self.request, self.vm

        if vm.status not in vm.STATUS_OPERATIONAL:
            raise VmIsNotOperational

        yyyymm, since, until, current_month = parse_yyyymm(self.yyyymm, vm.created.replace(tzinfo=None))

        _apiview_ = {'view': 'mon_vm_sla', 'method': request.method, 'hostname': vm.hostname, 'yyyymm': yyyymm}

        _since = int(since.strftime('%s'))
        _until = int(until.strftime('%s')) - 1
        args = (vm.hostname, yyyymm, vm.node_history(_since, _until))
        tidlock = 'mon_vm_sla vm:%s yyyymm:%s' % (vm.uuid, yyyymm)

        if current_month:
            cache_timeout = 300
        else:
            cache_timeout = 86400

        ter = t_mon_vm_sla.call(request, vm.owner.id, args, kwargs={'vm_uuid': vm.uuid}, meta={'apiview': _apiview_},
                                tidlock=tidlock, cache_result=tidlock, cache_timeout=cache_timeout)

        return mgmt_task_response(request, *ter, vm=vm, api_view=_apiview_, data=self.data)


class VmHistoryView(APIView):

    def __init__(self, request, hostname, graph_type, data):
        super(VmHistoryView, self).__init__(request)
        self.vm = get_vm(request, hostname, sr=('dc',))
        self.graph_type = graph_type
        self.data = data

    def get(self):
        request, vm, graph = self.request, self.vm, self.graph_type

        if not vm.is_zabbix_sync_active():
            raise ExpectationFailed('VM monitoring disabled')

        if vm.status not in vm.STATUS_OPERATIONAL:
            raise VmIsNotOperational

        # Validate graph identificator
        graph_category, item_id = MonVmHistorySerializer.parse_graph(vm, graph)

        try:
            if not graph_category:
                raise KeyError
            graph_settings = GRAPH_ITEMS.get_options(graph_category, vm)
        except KeyError:
            raise InvalidInput('Invalid graph')
        else:
            required_ostype = graph_settings.get('required_ostype', None)

            if required_ostype is not None and vm.ostype not in required_ostype:
                raise InvalidInput('Invalid OS type')

        _apiview_ = {'view': 'mon_vm_history', 'method': request.method, 'hostname': vm.hostname, 'graph': graph}

        ser = MonVmHistorySerializer(data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, vm=vm)

        result = ser.object.copy()
        result['desc'] = graph_settings.get('desc', '')
        result['hostname'] = vm.hostname
        result['graph'] = graph
        result['options'] = graph_settings.get('options', {})
        result['update_interval'] = graph_settings.get('update_interval', None)
        tidlock = 'mon_vm_history vm:%s graph:%s since:%d until:%d' % (vm.uuid, graph, round(ser.object['since'], -2),
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
        ter = t_mon_vm_history.call(request, vm.owner.id, (vm.uuid, items, history, result, items_search),
                                    kwargs={'vm_uuid': vm.uuid}, meta={'apiview': _apiview_}, tidlock=tidlock)
        # NOTE: cache_result=tidlock, cache_timeout=60)
        # Caching is disable here, because it makes no real sense.
        # The latest graphs must be fetched from zabbix and the older are requested only seldom.

        return mgmt_task_response(request, *ter, vm=vm, api_view=_apiview_, data=self.data)
