from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.utils.db import get_object
from api.node.image.api_views import NodeImageView
from vms.models import NodeStorage, Image

__all__ = ('node_image_list', 'node_image')


@api_view(('GET', 'DELETE'))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def node_image_list(request, hostname, zpool, data=None):
    """
    List (:http:get:`GET </node/(hostname)/storage/(zpool)/image>`) all images imported on a compute node storage or
    remove (:http:delete:`DELETE </node/(hostname)/storage/(zpool)/image>`) all unused images
    imported on a compute node storage.

    .. http:get:: /node/(hostname)/storage/(zpool)/image

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg zpool: **required** - Node storage pool name
        :type zpool: string
        :arg data.full: Return list of objects with all image details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Storage not found

    .. http:delete:: /node/(hostname)/storage/(zpool)/image

        .. note:: This API function will run \
:http:delete:`DELETE node_image </node/(hostname)/storage/(zpool)/image/(name)>` for every unused image.

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg zpool: **required** - Node storage pool name
        :type zpool: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Storage not found
        :status 423: Node is not operational

    """
    ns = get_object(request, NodeStorage, {'node__hostname': hostname, 'zpool': zpool},
                    exists_ok=True, noexists_fail=True, sr=('node',))
    images = ns.images.select_related('owner', 'dc_bound').order_by(*NodeImageView.get_order_by(data))
    node_image_view = NodeImageView(request, ns, images, data)

    if request.method == 'DELETE':
        return node_image_view.cleanup()
    else:
        return node_image_view.get(many=True)


@api_view(('GET', 'POST', 'DELETE'))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def node_image(request, hostname, zpool, name, data=None):
    """
    Show (:http:get:`GET </node/(hostname)/storage/(zpool)/image/(name)>`),
    import (:http:post:`POST </node/(hostname)/storage/(zpool)/image/(name)>`) or
    delete (:http:delete:`DELETE </node/(hostname)/storage/(zpool)/image/(name)>`)
    an image (name) on a compute node (hostname) storage (zpool).

    .. http:get:: /node/(hostname)/storage/(zpool)/image/(name)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg zpool: **required** - Node storage pool name
        :type zpool: string
        :arg name: **required** - Image name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Storage not found / Image not found

    .. http:post:: /node/(hostname)/storage/(zpool)/image/(name)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg zpool: **required** - Node storage pool name
        :type zpool: string
        :arg name: **required** - Image name
        :type name: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Storage not found / Image not found
        :status 406: Image already exists
        :status 423: Node is not operational
        :status 428: Image requires newer node version / Image requires newer node version

    .. http:delete:: /node/(hostname)/storage/(zpool)/image/(name)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg zpool: **required** - Node storage pool name
        :type zpool: string
        :arg name: **required** - Image name
        :type name: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Storage not found / Image not found
        :status 423: Node is not operational
        :status 428: Image is used by some VMs

    """
    ns = get_object(request, NodeStorage, {'node__hostname': hostname, 'zpool': zpool},
                    exists_ok=True, noexists_fail=True, sr=('node', 'storage'))
    attrs = {'name': name}

    if request.method != 'POST':
        attrs['nodestorage'] = ns

    img = get_object(request, Image, attrs, sr=('owner', 'dc_bound'), exists_ok=True, noexists_fail=True)

    return NodeImageView(request, ns, img, data).response()
