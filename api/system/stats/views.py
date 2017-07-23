from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.system.stats.api_views import SystemStatsView

__all__ = ('system_stats',)


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_stats(request, data=None):
    """
    Show (:http:get:`GET </system/stats>`) statistics about datacenters, compute nodes and virtual servers in the \
whole system.

    .. http:get:: /system/stats

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return SystemStatsView(request, data).get()
