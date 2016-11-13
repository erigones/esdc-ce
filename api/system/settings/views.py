from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.system.settings.api_views import SystemSettingsView

__all__ = ('system_settings_ssl_certificate',)


@api_view(('PUT',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_settings_ssl_certificate(request, data=None):
    """
    Change (:http:put:`PUT </system/settings/ssl-certificate>`) SSL certificate of Danube Cloud web management services.

    .. http:put:: /system/settings/ssl-certificate

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.cert: **required** - certificates and associated private keys in PEM format concatenated together
        :type data.cert: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
    """
    return SystemSettingsView(request, data).ssl_certificate()
