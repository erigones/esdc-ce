from api.decorators import api_view, request_data
from api.permissions import IsAdmin, IsSuperAdminOrReadOnly
from api.dc.storage.api_views import DcStorageView


__all__ = ('dc_storage_list', 'dc_storage')


@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_storage_list(request, data=None):
    """
    List (:http:get:`GET </dc/(dc)/storage>`) available node storages in current datacenter.

    .. http:get:: /dc/(dc)/storage

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg data.full: Return list of objects with all storage details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended storage details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``hostname``, ``zpool`` \
(default: ``hostname,zpool``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found
    """
    return DcStorageView(request, None, data).get(many=True)


# noinspection PyUnusedLocal
@api_view(('GET', 'POST', 'DELETE'))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_storage(request, zpool_node, data=None):
    """
    Show (:http:get:`GET </dc/(dc)/storage/(zpool@node)>`),
    create (:http:post:`POST </dc/(dc)/storage/(zpool@node)>`) or
    delete (:http:delete:`DELETE </dc/(dc)/storage/(zpool@node)>`)
    a node storage (zpool@node) association with a datacenter (dc).

    .. http:get:: /dc/(dc)/storage/(zpool@node)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg zpool@node: **required** - Storage pool name @ Compute node hostname
        :type zpool@node: string
        :arg data.extended: Display extended storage details (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Storage not found

    .. http:post:: /dc/(dc)/storage/(zpool@node)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg zpool@node: **required** - Storage pool name @ Compute node hostname
        :type zpool@node: string
        :status 201: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Storage not found
        :status 406: Storage already exists
        :status 428: Compute node is not available

    .. http:delete:: /dc/(dc)/storage/(zpool@node)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg zpool@node: **required** - Storage pool name @ Compute node hostname
        :type zpool@node: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Storage not found
        :status 428: Storage is used by some VMs / Storage is used by some VM backups

    """
    return DcStorageView(request, zpool_node, data).response()
