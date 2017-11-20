from api.mon.alerting.action.serializers import ActionSerializer

from api.mon.base.api_views import _MonBaseView

from api.api_views import APIView
from api.decorators import api_view, request_data, setting_required
from api.mon.alerting.action.tasks import mon_action_list
from api.permissions import IsAdmin
from api.status import HTTP_201_CREATED
from api.task.response import SuccessTaskResponse, FailureTaskResponse


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

    def get(self):
        return

    def post(self):
        ser = self.serializer(data=self.data, name=self.name)
        ser.request = self.request
        if ser.is_valid():
            # push
            return SuccessTaskResponse(self.request, ser.data, status=HTTP_201_CREATED, detail_dict=ser.detail_dict())
        else:
            return FailureTaskResponse(self.request, ser.errors)

    def put(self):
        return

    def delete(self):
        return


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def action_manage(request, name, data=None):
    return ActionView(request, name, data).response()
