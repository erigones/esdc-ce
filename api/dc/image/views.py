from api.decorators import api_view, request_data
from api.permissions import IsAdmin, IsSuperAdminOrReadOnly
from api.dc.image.api_views import DcImageView

__all__ = ('dc_image_list', 'dc_image')


@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_image_list(request, data=None):
    """
    List (:http:get:`GET </dc/(dc)/image>`) available server disk images in current datacenter.

    .. http:get:: /dc/(dc)/image

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg data.full: Return list of objects with all image details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found
    """
    return DcImageView(request, None, data).get(many=True)


# noinspection PyUnusedLocal
@api_view(('GET', 'POST', 'DELETE'))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_image(request, name, data=None):
    """
    Show (:http:get:`GET </dc/(dc)/image/(name)>`),
    create (:http:post:`POST </dc/(dc)/image/(name)>`) or
    delete (:http:delete:`DELETE </dc/(dc)/image/(name)>`)
    a server disk image (name) association with a datacenter (dc).

    .. http:get:: /dc/(dc)/image/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - Server disk image name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Image not found

    .. http:post:: /dc/(dc)/image/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - Server disk image name
        :type name: string
        :status 201: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Image not found
        :status 406: Image already exists

    .. http:delete:: /dc/(dc)/image/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - Server disk image name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Image not found
        :status 428: Image is used by some VMs

    """
    return DcImageView(request, name, data).response()
