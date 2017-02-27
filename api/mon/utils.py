from django.conf import settings

from api.task.internal import InternalTask
from api.task.response import mgmt_task_response
from vms.utils import AttrDict


class MonitoringGraph(AttrDict):
    """
    Monitoring graph configuration.
    """
    def __init__(self, name, **params):
        dict.__init__(self)
        self['name'] = name
        self['params'] = params


# noinspection PyAbstractClass
class MonInternalTask(InternalTask):
    """
    Internal zabbix tasks.
    """
    abstract = True

    def call(self, *args, **kwargs):
        # Monitoring is completely disabled
        if not settings.MON_ZABBIX_ENABLED:
            return None

        return super(MonInternalTask, self).call(*args, **kwargs)


def call_mon_history_task(request, task_function, view_fun_name, obj, serializer, data, graph, graph_settings):
    """Function that calls task_function callback and returns output mgmt_task_response()"""
    _apiview_ = {
        'view': view_fun_name,
        'method': request.method,
        'hostname': obj.hostname,
        'graph': graph,
        'graph_params': serializer.object.copy(),
     }

    result = serializer.object.copy()
    result['desc'] = graph_settings.get('desc', '')
    result['hostname'] = obj.hostname
    result['graph'] = graph
    result['options'] = graph_settings.get('options', {})
    result['update_interval'] = graph_settings.get('update_interval', None)
    tidlock = '%s obj:%s graph:%s item_id:%s since:%d until:%d' % (task_function.__name__,
                                                                   obj.uuid, graph, serializer.item_id,
                                                                   round(serializer.object['since'], -2),
                                                                   round(serializer.object['until'], -2))

    item_id = serializer.item_id

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
    ter = task_function.call(request, obj.owner.id, (obj.uuid, items, history, result, items_search),
                             meta={'apiview': _apiview_}, tidlock=tidlock)
    # NOTE: cache_result=tidlock, cache_timeout=60)
    # Caching is disable here, because it makes no real sense.
    # The latest graphs must be fetched from zabbix and the older are requested only seldom.

    return mgmt_task_response(request, *ter, obj=obj, api_view=_apiview_, data=data)
