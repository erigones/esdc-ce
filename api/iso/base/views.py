from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsAnyDcIsoAdmin
from api.iso.base.api_views import IsoView

__all__ = ('iso_list', 'iso_manage')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsAnyDcIsoAdmin,))
def iso_list(request, data=None):
    """
    List (:http:get:`GET </iso>`) all ISO images.

    .. http:get:: /iso

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |IsoAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with all ISO image details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended ISO image details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``created`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return IsoView(request, None, data).get(many=True)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcIsoAdmin,))
def iso_manage(request, name, data=None):
    """
    Show (:http:get:`GET </iso/(name)>`), create (:http:post:`POST </iso/(name)>`
    update (:http:put:`PUT </iso/(name)>`) or delete (:http:delete:`DELETE </iso/(name)>`)
    an ISO image.

    .. note:: All operations are currently performed only at the database level. \
ISO images need to be manually distributed across all compute nodes.

    .. http:get:: /iso/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |IsoAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - ISO image name
        :type name: string
        :arg data.extended: Display extended ISO image details (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: ISO image not found

    .. http:post:: /iso/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |IsoAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no| - Will be asynchronous in future
        :arg name: **required** - ISO image file name
        :type name: string
        :arg data.alias: Short ISO image name (default: ``name`` without ".iso")
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private) (default: 3)
        :type data.access: integer
        :arg data.owner: User that owns the ISO image (default: logged in user)
        :type data.owner: string
        :arg data.desc: ISO image description
        :type data.desc: string
        :arg data.ostype: Operating system type (null - all OS types, 1 - Linux VM, 2 - SunOS VM, 3 - BSD VM, \
4 - Windows VM) (default: null)
        :type data.ostype: integer
        :arg data.dc_bound: Whether the ISO image is bound to a datacenter (requires |SuperAdmin| permission) \
(default: true)
        :type data.dc_bound: boolean
        :arg data.dc: Name of the datacenter the ISO image will be attached to (**required** if DC-bound)
        :type data.dc: string
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found
        :status 406: ISO image already exists

    .. http:put:: /iso/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |IsoAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - ISO image name
        :type name: string
        :arg data.alias: Short ISO image name
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private)
        :type data.access: integer
        :arg data.owner: User that owns the ISO image
        :type data.owner: string
        :arg data.desc: ISO image description
        :type data.desc: string
        :arg data.ostype: Operating system type (null - all OS types, 1 - Linux VM, 2 - SunOS VM, 3 - BSD VM, \
4 - Windows VM)
        :type data.ostype: integer
        :arg data.dc_bound: Whether the ISO image is bound to a datacenter (requires |SuperAdmin| permission)
        :type data.dc_bound: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: ISO image not found

    .. http:delete:: /iso/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |IsoAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no| - Will be asynchronous in future
        :arg name: **required** - ISO image name
        :type name: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: ISO image not found

    """
    return IsoView(request, name, data).response()
