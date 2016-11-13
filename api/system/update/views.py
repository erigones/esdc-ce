from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.system.update.api_views import UpdateView

__all__ = ('system_update',)


@api_view(('PUT',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_update(request, data=None):
    """
    Install (:http:put:`PUT </system/update>`) Danube Cloud updates.

    .. http:put:: /system/update

        .. note:: Danube Cloud application services will be automatically restarted after successful \
update installation.

        .. note:: Update of Danube Cloud on all :http:put:`compute nodes </system/node/(hostname)/update>` should \
be performed after successful system update.

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.version: **required** - version to which system should be updated
        :type data.version: string
        :arg data.key: X509 private key file used for authentication against EE git server. \
Please note that file MUST contain standard x509 file BEGIN/END header/footer. \
If not present, cached key file "update.key" will be used
        :type data.key: string
        :arg data.cert: X509 private cert file used for authentication against EE git server. \
Please note that file MUST contain standard x509 file BEGIN/END headers/footer. \
If not present, cached cert file "update.crt" will be used.
        :type data.cert: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 423: Task is already running
        :status 428: System is already up-to-date
    """
    return UpdateView(request, data).response()
