from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.system.service.api_views import ServiceStatusView

__all__ = ('system_service_status_list', 'system_service_status')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_service_status_list(request, data=None):
    """
    Get (:http:get:`GET </system/service/status>`) status of all system services.

    .. http:get:: /system/service/status

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
    """
    return ServiceStatusView(request, None, data).get()


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_service_status(request, name, data=None):
    """
    Get (:http:get:`GET </system/service/(name)/status>`) system service status.

    .. http:get:: /system/service/(name)/status

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Service name
        :type name: string
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Service not found

    """
    return ServiceStatusView(request, name, data).response()
