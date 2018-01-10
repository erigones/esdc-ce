from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.system.update.api_views import UpdateView

__all__ = ('system_update',)


@api_view(('PUT',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_update(request, data=None):
    """
    Update (:http:put:`PUT </system/update>`) Danube Cloud to a selected version.

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
            * |async-yes|
        :arg data.version: **required** - git tag (e.g. ``v2.6.5``) or git commit to which the system should be updated
        :type data.version: string
        :arg data.force: Whether to perform the update operation even though the software is already at selected version
        :type data.force: boolean
        :arg data.key: X509 private key file used for authentication against EE git server. \
Please note that file MUST contain standard x509 file BEGIN/END header/footer. \
If not present, cached key file "update.key" will be used
        :type data.key: string
        :arg data.cert: X509 private cert file used for authentication against EE git server. \
Please note that file MUST contain standard x509 file BEGIN/END headers/footer. \
If not present, cached cert file "update.crt" will be used.
        :type data.cert: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 428: System is already up-to-date
    """
    return UpdateView(request, data).response()
