from api.mon.base.api_views import _MonBaseView

from api.api_views import APIView
from api.decorators import api_view, request_data, setting_required
from api.mon.alerting.action.tasks import mon_action_list
from api.permissions import IsAdmin


class MonActionView(_MonBaseView):
    api_view_name = 'action_list'
    mgmt_task = mon_action_list


@api_view(('GET',))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def action_list(request, data=None):
    return MonActionView(request, data).get()


class ActionView(APIView):
    def __init__(self, request, name, data):
        super(ActionView, self).__init__(request)

    def get(self):
        return

    def post(self):
        return

    def put(self):
        return

    def delete(self):
        return


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def action_manage(request, name, data=None):
    return ActionView(request, name, data).response()
