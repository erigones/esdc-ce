from api.vm.messages import LOG_ACTION_CREATE
from que import TG_DC_BOUND

from api.mon.alerting.action.serializers import ActionSerializer, ActionUpdateSerializer

from api.mon.base.api_views import MonBaseView

from api.api_views import APIView
from api.decorators import api_view, request_data, setting_required
from api.mon.alerting.action.tasks import mon_action_list, mon_action_delete, mon_action_update, mon_action_create, \
    mon_action_get
from api.permissions import IsAdmin
from api.task.response import FailureTaskResponse, mgmt_task_response


class MonActionView(MonBaseView):
    api_view_name = 'action_list'
    mgmt_task = mon_action_list


@api_view(('GET',))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def action_list(request, data=None):
    """
    Get (:http:get:`GET </mon/action>`) monitoring actions.

    .. http:get:: /mon/action

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin| - ``dc_bound=true``
        :Asynchronous?:
            * |async-yes| - List of all monitoring alerts is retrieved from monitoring server
            * |async-no| - List of all monitoring alerts is retrieved from cache


        :arg data.dc_bound: Execute as DC unbound in the main virtual datacenter (default: true)
        :type data.dc_bound: boolean

        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
    """
    return MonActionView(request, data).get()


class ActionView(APIView):
    def __init__(self, request, name, data):
        super(ActionView, self).__init__(request)
        self.data = data
        self.name = name

    def get(self):
        result = mon_action_get.call(self.request, None, (self.request.dc.id, self.name), tg=TG_DC_BOUND)
        return mgmt_task_response(self.request, *result, msg=LOG_ACTION_CREATE, detail_dict={'name': self.name},
                                  obj=self.request.dc)

    def post(self):
        # tidlock = '%s:%s:%s' % ('mon_action_create', self.request.dc.id, self.dc_bound)
        # add _apiview_
        self.data['name'] = self.name
        ser = ActionSerializer(data=self.data, name=self.name, context=self.request)
        ser.request = self.request
        if ser.is_valid():
            result = mon_action_create.call(
                self.request,
                None,
                (self.request.dc.id, ser.data),
                tg=TG_DC_BOUND,
            )
            return mgmt_task_response(self.request, *result, msg=LOG_ACTION_CREATE, detail_dict=ser.detail_dict(),
                                      obj=self.request.dc)
        else:
            return FailureTaskResponse(self.request, ser.errors)

    def put(self):
        ser = ActionUpdateSerializer(data=self.data, context=self.request)
        ser.request = self.request
        if ser.is_valid():
            # Send only those items that were changed in the request
            data = {key: value for key, value in ser.data.items() if key in self.data}
            data['name'] = self.name

            result = mon_action_update.call(self.request,
                                            None,
                                            (self.request.dc.id, data),
                                            tg=TG_DC_BOUND,
                                            )
            return mgmt_task_response(self.request, *result, msg=LOG_ACTION_CREATE, detail_dict=data,
                                      obj=self.request.dc)
        else:
            return FailureTaskResponse(self.request, ser.errors)

    def delete(self):
        result = mon_action_delete.call(self.request,
                                        None,
                                        (self.request.dc.id, self.name),
                                        tg=TG_DC_BOUND,
                                        )
        return mgmt_task_response(self.request, *result, msg=LOG_ACTION_CREATE, obj=self.request.dc)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def action_manage(request, name, data=None):
    """
    Show (:http:get:`GET </mon/action/(action name)>`),
    create (:http:post:`POST </mon/action/(action name)>`),
    remove (:http:delete:`DELETE </mon/action/(action name)>`),
    update (:http:put:`PUT </mon/action/(action name)>`)
    a monitoring action.

    .. http:get::  /mon/action/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg name: **required** - Monitoring action name
        :type name: string

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden

    .. http:post:: /mon/action/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg name: **required** - Monitoring action name
        :type name: string
        :arg data.hostgroups: **required** - Host groups that triggers an alert
        :type data.hostgroups: list
        :arg data.usergroups: **required** - User groups that should receive a notifications
        :type data.usergroups: list
        :arg data.message_subject: **required** - Subject of the notification message (default: as in zabbix documentation)
        :type data.message_subject: string
        :arg data.message_text: **required** - Text of the notification message (default: as in zabbix documentation)
        :type data.message_text: string
        :arg data.recovery_message_enabled: - Enable recovery message (default: false)
        :type data.recovery_message_enabled: bool
        :arg data.recovery_message_subject: - Recovery message subject (default: disabled, as in zabbix documentation)
        :type data.recovery_message_subject: string
        :arg data.recovery_message_text: -  Recovery message text (default: disabled, as in zabbix documentation)
        :type data.recovery_message_text: string
        :arg data.action_enabled: - Enable or disable the action temporarily without the need to delete it (default: true)
        :type data.action_enabled: bool
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden

    .. http:put:: /mon/action/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg name: **required** - Monitoring action name
        :type name: string
        :arg data.hostgroups: - Host groups that triggers an alert
        :type data.hostgroups: list
        :arg data.usergroups: - User groups that should receive a notifications
        :type data.usergroups: list
        :arg data.message_subject: - Subject of the notification message
        :type data.message_subject: string
        :arg data.message_text: - Text of the notification message
        :type data.message_text: string
        :arg data.recovery_message_enabled: - Enable recovery message
        :type data.recovery_message_enabled: bool
        :arg data.recovery_message_subject: - Recovery message subject
        :type data.recovery_message_subject: string
        :arg data.recovery_message_text: -  Recovery message text
        :type data.recovery_message_text: string
        :arg data.action_enabled: - Enable or disable the action temporarily without the need to delete it
        :type data.action_enabled: bool

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden

    .. http:delete:: /mon/action/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg name: **required** - Monitoring action name
        :type name: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden

    """
    return ActionView(request, name, data).response()
