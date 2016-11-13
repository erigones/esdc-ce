from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsAnyDcImageImportAdmin
from api.imagestore.image.api_views import ImageStoreImageView

__all__ = ('imagestore_image_list', 'imagestore_image_manage')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsAnyDcImageImportAdmin,))
def imagestore_image_list(request, name, data=None):
    """
    List (:http:get:`GET </imagestore/(name)/image>`) all disk images available on remote image repository.

    .. http:get:: /imagestore/(name)/image

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
        :status 404: ImageStore not found
    """
    return ImageStoreImageView(request, name, None, data).get(many=True)


@api_view(('GET', 'POST'))
@request_data_defaultdc(permissions=(IsAnyDcImageImportAdmin,))
def imagestore_image_manage(request, name, uuid, data=None):
    """
    Show (:http:get:`GET </imagestore/(name)/image/(uuid)>`) disk image metadata or
    import (:http:post:`POST </imagestore/(name)/image/(uuid)>`) disk image from remote image repository.

    .. http:get:: /imagestore/(name)/image/(uuid)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |ImageImportAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Image repository name
        :type name: string
        :arg uuid: **required** - Image uuid
        :type uuid: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: ImageStore not found / Image not found

    .. http:post:: /imagestore/(name)/image/(uuid)

        This calls the :http:post:`POST /image/(name) </image/(name)>` API function so the function properties, \
response and possible status codes are identical. It also accepts the same parameters as \
:http:post:`POST /image/(name) </image/(name)>` except of ``manifest_url`` and ``file_url``, which are \
defined by the repository the image is imported from. Also the ``name`` parameter is not required as it is set to \
a default value retrieved from the disk image metadata.
    """
    return ImageStoreImageView(request, name, uuid, data).response()
