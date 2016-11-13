from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.node.storage.utils import get_node_storages, get_node_storage
from api.node.storage.api_views import NodeStorageView

__all__ = ('node_storage_list', 'node_storage')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def node_storage_list(request, hostname, data=None):
    """
    List (:http:get:`GET </node/(hostname)/storage>`) all node storages.

    .. http:get:: /node/(hostname)/storage

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg data.full: Return list of objects with node storage details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended node storage details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``zpool``, ``created`` (default: ``zpool``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Node not found
    """
    nss = get_node_storages(request, hostname, order_by=NodeStorageView.get_order_by(data))

    return NodeStorageView(request, data=data).get(nss, many=True)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def node_storage(request, hostname, zpool, data=None):
    """
    Show (:http:get:`GET </node/(hostname)/storage/(zpool)>`),
    create (:http:post:`POST </node/(hostname)/storage/(zpool)>`)
    update (:http:put:`PUT </node/(hostname)/storage/(zpool)>`) or
    delete (:http:delete:`DELETE </node/(hostname)/storage/(zpool)>`)
    a node storage.

    .. http:get:: /node/(hostname)/storage/(zpool)

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
        :arg data.extended: Display extended node storage details (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Node not found / Storage not found

    .. http:post:: /node/(hostname)/storage/(zpool)

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
        :arg data.alias: Short node storage name (default: ``zpool``)
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private) (default: 3)
        :type data.access: integer
        :arg data.owner: User that owns the node storage (default: logged in user)
        :type data.owner: string
        :arg data.type: Node storage type (1 - Local, 3 - iSCSI, 4 - Fiber Channel) (default: 1)
        :type data.type: integer
        :arg data.size_coef: Coefficient for calculating the maximum amount of disk space available \
for virtual machines (default: 0.6)
        :type data.size_coef: float
        :arg data.desc: Node storage description
        :type data.desc: string
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found
        :status 406: Storage already exists

    .. http:put:: /node/(hostname)/storage/(zpool)

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
        :arg data.alias: Short node storage name
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private)
        :type data.access: integer
        :arg data.owner: User that owns the node storage
        :type data.owner: string
        :arg data.type: Node storage type (1 - Local, 3 - iSCSI, 4 - Fiber Channel)
        :type data.type: integer
        :arg data.size_coef: Coefficient for calculating the maximum amount of disk space available \
for virtual machines
        :type data.size_coef: float
        :arg data.desc: Node storage description
        :type data.desc: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found / Storage not found

    .. http:delete:: /node/(hostname)/storage/(zpool)

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
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found / Storage not found
        :status 428: Storage is used by some VMs / Storage is used by some VM backups

    """
    return NodeStorageView(request, data=data).response(get_node_storage(request, hostname, zpool))
