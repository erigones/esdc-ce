from api.decorators import api_view, request_data, setting_required
from api.permissions import IsAdmin, IsMonitoringAdmin
from api.mon.alerting.action.api_views import MonActionView


@api_view(('GET',))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def mon_action_list(request, data=None):
    """
    Get (:http:get:`GET </mon/action>`) list of monitoring actions.

    .. http:get:: /mon/action

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |IsAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg data.full: Return list of objects with all monitoring action details (default: false)
        :type data.full: boolean

        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
    """
    return MonActionView(request, None, data).get(many=True)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsMonitoringAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def mon_action_manage(request, action_name, data=None):
    """
    Show (:http:get:`GET </mon/action/(action_name)>`),
    create (:http:post:`POST </mon/action/(action_name)>`),
    remove (:http:delete:`DELETE </mon/action/(action_name)>`) or
    update (:http:put:`PUT </mon/action/(action_name)>`)
    a monitoring action.

    .. http:get::  /mon/action/(action_name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |MonitoringAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg action_name: **required** - Monitoring action name
        :type action_name: string

        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden

    .. http:post:: /mon/action/(action_name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |MonitoringAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg action_name: **required** - Monitoring action name
        :type action_name: string
        :arg data.hostgroups: **required** - Host groups that trigger an alert
        :type data.hostgroups: array
        :arg data.usergroups: **required** - User groups that should receive a notifications
        :type data.usergroups: array
        :arg data.message_subject: Subject of the notification message (default: as in Zabbix documentation)
        :type data.message_subject: string
        :arg data.message_text: Text of the notification message (default: as in Zabbix documentation)
        :type data.message_text: string
        :arg data.recovery_message_enabled: Enable recovery message (default: false)
        :type data.recovery_message_enabled: boolean
        :arg data.recovery_message_subject: Recovery message subject (default: as in Zabbix documentation)
        :type data.recovery_message_subject: string
        :arg data.recovery_message_text: Recovery message text (default: as in Zabbix documentation)
        :type data.recovery_message_text: string
        :arg data.enabled: Enable or disable the action temporarily without the need to delete it (default: true)
        :type data.enabled: boolean

        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden

    .. http:put:: /mon/action/(action_name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |MonitoringAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg action_name: **required** - Monitoring action name
        :type action_name: string
        :arg data.hostgroups: Host groups that trigger an alert
        :type data.hostgroups: array
        :arg data.usergroups: User groups that should receive a notifications
        :type data.usergroups: array
        :arg data.message_subject: Subject of the notification message
        :type data.message_subject: string
        :arg data.message_text: Text of the notification message
        :type data.message_text: string
        :arg data.recovery_message_enabled: Enable recovery message
        :type data.recovery_message_enabled: boolean
        :arg data.recovery_message_subject: Recovery message subject
        :type data.recovery_message_subject: string
        :arg data.recovery_message_text: Recovery message text
        :type data.recovery_message_text: string
        :arg data.enabled: Enable or disable the action temporarily without the need to delete it
        :type data.enabled: boolean

        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden

    .. http:delete:: /mon/action/(action_name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |MonitoringAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg action_name: **required** - Monitoring action name
        :type action_name: string

        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden

    """
    return MonActionView(request, action_name, data).response()
