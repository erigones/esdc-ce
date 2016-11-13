from api.decorators import api_view, request_data
from api.permissions import IsAdmin, IsSuperAdminOrReadOnly
from api.dc.iso.api_views import DcIsoView

__all__ = ('dc_iso_list', 'dc_iso')


@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_iso_list(request, data=None):
    """
    List (:http:get:`GET </dc/(dc)/iso>`) available ISO images in current datacenter.

    .. http:get:: /dc/(dc)/iso

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg data.full: Return list of objects with all ISO image details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found
    """
    return DcIsoView(request, None, data).get(many=True)


# noinspection PyUnusedLocal
@api_view(('GET', 'POST', 'DELETE'))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_iso(request, name, data=None):
    """
    Show (:http:get:`GET </dc/(dc)/iso/(name)>`),
    create (:http:post:`POST </dc/(dc)/iso/(name)>`) or
    delete (:http:delete:`DELETE </dc/(dc)/iso/(name)>`)
    a ISO image (name) association with a datacenter (dc).

    .. http:get:: /dc/(dc)/iso/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - ISO image name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / ISO image not found

    .. http:post:: /dc/(dc)/iso/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - ISO image name
        :type name: string
        :status 201: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / ISO image not found
        :status 406: ISO image already exists

    .. http:delete:: /dc/(dc)/iso/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - ISO image name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / ISO image not found

    """
    return DcIsoView(request, name, data).response()
