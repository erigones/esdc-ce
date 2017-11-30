from api.vm.messages import LOG_ACTION_CREATE
from que import TG_DC_BOUND

from api.mon.alerting.action.serializers import ActionSerializer

from api.mon.base.api_views import _MonBaseView

from api.api_views import APIView
from api.decorators import api_view, request_data, setting_required
from api.mon.alerting.action.tasks import mon_action_list, mon_action_delete, mon_action_update, mon_action_create
from api.permissions import IsAdmin
from api.task.response import FailureTaskResponse, TaskResponse


class MonActionView(_MonBaseView):
    api_view_name = 'action_list'
    mgmt_task = mon_action_list


@api_view(('GET',))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def action_list(request, data=None):
    return MonActionView(request, data).get()


class ActionView(APIView):
    serializer = ActionSerializer

    def __init__(self, request, name, data):
        super(ActionView, self).__init__(request)
        self.data = data
        self.name = name
        self.data['name']=name

    def get(self):
        return

    def post(self):
        # tidlock = '%s:%s:%s' % ('mon_action_create', self.request.dc.id, self.dc_bound)

        ser = self.serializer(data=self.data, name=self.name, context=self.request)
        ser.request = self.request
        if ser.is_valid():
            result = mon_action_create.call(self.request,
                                            None,
                                            (self.request.dc.id, ser.data),
                                            tg=TG_DC_BOUND,
                                            )
            return TaskResponse(self.request, task_id=result[0], msg=LOG_ACTION_CREATE, detail_dict=ser.data,
                                obj=self.request.dc)
        else:
            return FailureTaskResponse(self.request, ser.errors)

    def put(self):
        ser = self.serializer(data=self.data, name=self.name, context=self.request)
        ser.request = self.request
        if ser.is_valid():
            result = mon_action_update.call(self.request,
                                            None,
                                            (self.request.dc.id, ser.data),
                                            tg=TG_DC_BOUND,
                                            )
            return TaskResponse(self.request, task_id=result[0], msg=LOG_ACTION_CREATE, detail_dict=ser.data,
                                obj=self.request.dc)
        else:
            return FailureTaskResponse(self.request, ser.errors)

    def delete(self):
        result = mon_action_delete.call(self.request,
                                        None,
                                        (self.request.dc.id, self.name),
                                        tg=TG_DC_BOUND,
                                        )
        return TaskResponse(self.request, task_id=result[0], msg=LOG_ACTION_CREATE,
                            obj=self.request.dc)



@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def action_manage(request, name, data=None):
    return ActionView(request, name, data).response()
