from api.decorators import api_view, request_data, request_data_defaultdc, setting_required
from api.permissions import IsAdmin, IsSuperAdmin
from api.mon.base.api_views import MonTemplateView, MonHostgroupView, MonActionView

__all__ = ('mon_template_list', 'mon_node_template_list', 'mon_hostgroup_list', 'mon_node_hostgroup_list')


@api_view(('GET',))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def mon_template_list(request, data=None):
    """
    Get (:http:get:`GET </mon/template>`)

    .. http:get:: /mon/template

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes| - List of monitoring templates is retrieved from monitoring server
            * |async-no| - List of monitoring templates is retrieved from cache
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
    """
    return MonTemplateView(request, data).get()


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def mon_node_template_list(request, data=None):
    """
    This is an internal API call. It does the same thing as mon_template_list, but is DC-unbound and forces the DC
    to be a default DC. Used by the GUI to display a list of templates suitable for a compute node.
    """
    return MonTemplateView(request, data, dc_bound=False).get()


@api_view(('GET',))
@request_data(permissions=(IsAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def mon_hostgroup_list(request, data=None):
    """
    Get (:http:get:`GET </mon/hostgroup>`)

    .. http:get:: /mon/hostgroup

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes| - List of monitoring hostgroups is retrieved from monitoring server
            * |async-no| - List of monitoring hostgroups is retrieved from cache
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
    """
    return MonHostgroupView(request, data).get()


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
@setting_required('MON_ZABBIX_ENABLED')
def mon_node_hostgroup_list(request, data=None):
    """
    This is an internal API call. It does the same thing as mon_hostgroup_list, but is DC-unbound and forces the DC
    to be a default DC. Used by the GUI to display a list of hostgroups suitable for a compute node.
    """
    return MonHostgroupView(request, data, dc_bound=False).get()
