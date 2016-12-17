from api.decorators import api_view, request_data_defaultdc, request_data
from api.permissions import IsImageAdmin, IsAnyDcImageAdmin
from api.image.base.api_views import ImageView

__all__ = ('image_list', 'image_manage')  # image_snapshot is part of api.vm.snapshot.views


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsAnyDcImageAdmin,))
def image_list(request, data=None):
    """
    List (:http:get:`GET </image>`) all server disk images.

    .. http:get:: /image

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |ImageAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with all server disk image details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended server disk image details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``created`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return ImageView(request, None, data).get(many=True)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcImageAdmin,))
def image_manage(request, name, data=None):
    """
    Show (:http:get:`GET </image/(name)>`),
    import (:http:post:`POST </image/(name)>`),
    update (:http:put:`PUT </image/(name)>`) or
    delete (:http:delete:`DELETE </image/(name)>`) a server disk image.

    .. http:get:: /image/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |ImageAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Server disk image name
        :type name: string
        :arg data.extended: Display extended disk image details (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Image not found

    .. http:post:: /image/(name)

        .. note:: You can also import images from remote disk image repositories by using the \
:http:post:`POST /imagestore/(name)/image/(uuid) </imagestore/(name)/image/(uuid)>` API function.

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |ImageImportAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-yes|
        :arg name: **required** - Server disk image name
        :type name: string
        :arg data.manifest_url: **required** - Disk image manifest URL
        :type data.manifest_url: string
        :arg data.file_url: Optional image file URL (will be assembled from manifest URL if not provided)
        :type data.file_url: string
        :arg data.alias: Short image name (default: ``name``)
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private, 4 - Deleted) (default: 3)
        :type data.access: integer
        :arg data.owner: User that owns the image (default: logged in user)
        :type data.owner: string
        :arg data.desc: Image description (default: read from manifest)
        :type data.desc: string
        :arg data.version: Image version (default: read from manifest)
        :type data.version: string
        :arg data.resize: Whether the image is able to resize the disk during an initial start or deploy process \
(default: read from manifest / true for OS zones, otherwise false)
        :type data.resize: boolean
        :arg data.deploy: Whether the image is able to shut down the server after an initial start \
(default: read from manifest / false)
        :type data.deploy: boolean
        :arg data.tags: Image tags will be inherited by VMs which will use this image (default: read from manifest)
        :type data.tags: array
        :arg data.dc_bound: Whether the disk image is bound to a datacenter (requires |SuperAdmin| permission) \
(default: true)
        :type data.dc_bound: boolean
        :arg data.dc: Name of the datacenter the disk image will be attached to (**required** if DC-bound)
        :type data.dc: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found
        :status 406: Image already exists
        :status 423: Node is not operational
        :status 417: Image status is not OK
        :status 428: Image server is not available

    .. http:put:: /image/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |ImageAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-yes| - Image is updated on image server when one of the following attributes has changed: \
``name``, ``alias``, ``version``, ``access``, ``desc``
            * |async-no| - Image is updated in DB only when none of the following attributes was changed: \
``name``, ``alias``, ``version``, ``access``, ``desc``
        :arg name: **required** - Server disk image name
        :type name: string
        :arg data.alias: Short image name
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private, 4 - Deleted)
        :type data.access: integer
        :arg data.owner: User that owns the image
        :type data.owner: string
        :arg data.desc: Image description
        :type data.desc: string
        :arg data.version: Image version
        :type data.version: string
        :arg data.resize: Whether the image is able to resize the disk during an initial start or deploy process
        :type data.resize: boolean
        :arg data.deploy: Whether the image is able to shut down the server after an initial start
        :type data.deploy: boolean
        :arg data.tags: Image tags will be inherited by VMs which will use this image
        :type data.tags: array
        :arg data.dc_bound: Whether the image is bound to a datacenter (requires |SuperAdmin| permission)
        :type data.dc_bound: boolean
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Image not found
        :status 423: Node is not operational
        :status 417: Image status is not OK
        :status 428: Image server is not available

    .. http:delete:: /image/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |ImageAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-yes|
        :arg name: **required** - Server disk image name
        :type name: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Image not found
        :status 423: Node is not operational
        :status 417: Image status is not OK
        :status 428: Image is used by some VMs / Image server is not available
    """
    return ImageView(request, name, data).response()


@api_view(('POST',))
@request_data(permissions=(IsImageAdmin,))
def image_snapshot(request, hostname, snapname, name, data=None):
    """
    Create (:http:post:`POST </vm/(hostname)/snapshot/(snapname)/image/(name)>`)
    a server disk image from a disk snapshot.

    .. http:post:: /vm/(hostname)/snapshot/(snapname)/image/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |ImageAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg name: **required** - Server disk image name
        :type name: string
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg snapname: **required** - Snapshot name
        :type snapname: string
        :arg data.disk_id: **required** - Disk number/ID (default: 1)
        :type data.disk_id: integer
        :arg data.alias: Short image name (default: ``name``)
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private, 4 - Deleted) (default: 3)
        :type data.access: integer
        :arg data.owner: User that owns the image (default: logged in user)
        :type data.owner: string
        :arg data.desc: Image description
        :type data.desc: string
        :arg data.version: Image version (default: 1.0)
        :type data.version: string
        :arg data.resize: Whether the image is able to resize the disk during an initial start or deploy process \
(default: false)
        :type data.resize: boolean
        :arg data.deploy: Whether the image is able to shut down the server after an initial start (default: false)
        :type data.deploy: boolean
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: Image already exists
        :status 412: Invalid disk_id
        :status 423: Node is not operational / VM is not operational
        :status 417: Image status is not OK / VM snapshot status is not OK
        :status 428: Image server is not available
    """
    from api.utils.db import get_object
    from api.vm.utils import get_vm
    from api.vm.snapshot.utils import get_disk_id
    from vms.models import Snapshot

    vm = get_vm(request, hostname, exists_ok=True, noexists_fail=True)
    disk_id, real_disk_id, zfs_filesystem = get_disk_id(request, vm, data)
    snap = get_object(request, Snapshot, {'name': snapname, 'vm': vm, 'disk_id': real_disk_id},
                      exists_ok=True, noexists_fail=True)

    assert zfs_filesystem == snap.zfs_filesystem

    return ImageView(request, name, data).create(vm, snap)
