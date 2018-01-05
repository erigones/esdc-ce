from api.task.response import FailureTaskResponse
from api.mon.messages import LOG_MON_ACTION_CREATE, LOG_MON_ACTION_UPDATE, LOG_MON_ACTION_DELETE
from api.mon.base.api_views import MonBaseView
from api.mon.alerting.action.serializers import ActionSerializer
from api.mon.alerting.action.tasks import (mon_action_list, mon_action_get, mon_action_delete, mon_action_update,
                                           mon_action_create)


class MonActionView(MonBaseView):
    api_object_identifier = 'action_name'
    api_view_name_list = 'mon_action_list'
    api_view_name_manage = 'mon_action_manage'

    def get(self, many=False):
        if many:
            task = mon_action_list
            task_kwargs = {'full': self.full, 'extended': self.extended}
        else:
            task = mon_action_get
            task_kwargs = {}

        return self._create_task_and_response(task, task_kwargs=task_kwargs)

    def post(self):
        self.data['name'] = self.name
        ser = ActionSerializer(self.request, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors)

        task_kwargs = {'action_data': ser.data}  # all data

        return self._create_task_and_response(mon_action_create, task_kwargs=task_kwargs, msg=LOG_MON_ACTION_CREATE,
                                              detail_dict=ser.detail_dict(force_full=True))

    def put(self):
        self.data['name'] = self.name
        ser = ActionSerializer(self.request, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors)

        all_data = ser.data
        # only user provided data
        task_kwargs = {'action_data': {key: ser.data[key] for key in ser.init_data if key in all_data}}

        return self._create_task_and_response(mon_action_update, task_kwargs=task_kwargs, msg=LOG_MON_ACTION_UPDATE,
                                              detail_dict=ser.detail_dict(force_update=True))

    def delete(self):
        return self._create_task_and_response(mon_action_delete, msg=LOG_MON_ACTION_DELETE,
                                              detail_dict={'name': self.name})
