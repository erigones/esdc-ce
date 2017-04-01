from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsAnyDcImageImportAdmin
from api.imagestore.base.api_views import ImageStoreView

__all__ = ('imagestore_list', 'imagestore_manage')


@api_view(('GET', 'PUT'))
@request_data_defaultdc(permissions=(IsAnyDcImageImportAdmin,))
def imagestore_list(request, data=None):
    """
    List (:http:get:`GET </imagestore>`) or
    refresh (:http:put:`PUT </imagestore>`) information about disk image repositories.

    .. note:: Disk image repositories can be configured by modifying the \
:http:put:`VMS_IMAGE_REPOSITORIES </dc/(dc)/settings>` global setting.

    .. note:: If a global image server (:http:put:`VMS_IMAGE_VM </dc/(dc)/settings>`) is configured in the system, \
the list will automatically include a local repository named after the image server.

    .. http:get:: /imagestore

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |ImageImportAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with all image repository details (default: false)
        :type data.full: boolean
        :status 200: SUCCESS
        :status 403: Forbidden

    .. http:put:: /imagestore

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |ImageImportAdmin|
        :Asynchronous?:
            * |async-no|
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 423: Task is already running
    """
    return ImageStoreView(request, None, data, many=True).response()


@api_view(('GET', 'PUT'))
@request_data_defaultdc(permissions=(IsAnyDcImageImportAdmin,))
def imagestore_manage(request, name, data=None):
    """
    Show (:http:get:`GET </imagestore/(name)>`) or
    refresh (:http:put:`PUT </imagestore/(name)>`) information about a disk image repository.

    .. note:: Disk image repositories can be configured by modifying the \
:http:put:`VMS_IMAGE_REPOSITORIES </dc/(dc)/settings>` global setting.

    .. http:get:: /imagestore/(name)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |ImageImportAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Image repository name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: ImageStore not found

    .. http:put:: /imagestore/(name)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |ImageImportAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Image repository name
        :type name: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: ImageStore not found
        :status 423: Task is already running
    """
    return ImageStoreView(request, name, data, many=False).response()
