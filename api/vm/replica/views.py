from api.permissions import IsAdminOrReadOnly
from api.decorators import api_view, request_data, setting_required
from api.vm.replica.vm_replica import VmReplica
from api.vm.replica.vm_replica_action import VmReplicaFailover, VmReplicaReinit

__all__ = ('vm_replica_list', 'vm_replica', 'vm_replica_failover', 'vm_replica_reinit')


#: vm_status:   GET: -
@api_view(('GET',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vms() = IsVmOwner
@setting_required('VMS_VM_REPLICATION_ENABLED')
def vm_replica_list(request, hostname_or_uuid, data=None):
    """
    List (:http:get:`GET </vm/(hostname_or_uuid)/replica>`) current VM replicas.

    .. http:get:: /vm/(hostname_or_uuid)/replica

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.full: Return list of objects with all VM replica details (default: false)
        :type data.full: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
    """
    return VmReplica(request, hostname_or_uuid, None, data).get(many=True)


#: vm_status:   GET: -
#: vm_status:  POST: stopped, running
#: vm_status:   PUT: stopped, stopping, running
#: vm_status:DELETE: stopped, stopping, running
@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vms() = IsVmOwner
@setting_required('VMS_VM_REPLICATION_ENABLED')
def vm_replica(request, hostname_or_uuid, repname=None, data=None):
    """
    Show (:http:get:`GET </vm/(hostname_or_uuid)/replica/(repname)>`),
    create (:http:post:`POST </vm/(hostname_or_uuid)/replica/(repname)>`),
    remove (:http:delete:`DELETE </vm/(hostname_or_uuid)/replica/(repname)>`) or
    update (:http:put:`PUT </vm/(hostname_or_uuid)/replica/(repname)>`)
    a VM replica.

    .. note:: One slave server takes up the same amount of datacenter/compute node resources as master server.

    .. http:get:: /vm/(hostname_or_uuid)/replica/(repname)

        Display slave VM info.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg repname: **required** - Slave server identifier
        :type repname: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Slave VM not found


    .. http:post:: /vm/(hostname_or_uuid)/replica/(repname)

        Create slave VM and replication service on target node.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg repname: **required** - Slave server identifier
        :type repname: string
        :arg data.node: **required** - Target compute node hostname
        :type data.node: string
        :arg data.root_zpool: New zpool for the VM zone or OS zone including data disk
        :type data.root_zpool: string
        :arg data.disk_zpools: New zpools for VM's disks (``{disk_id: zpool}``)
        :type data.disk_zpools: dict
        :arg data.reserve_resources: Whether to reserve resources (vCPU, RAM) on target compute node (default: true); \
**NOTE**: When disabled, the resources must be available (and will be reserved) before the \
:http:put:`failover action </vm/(hostname_or_uuid)/replica/(repname)/failover>`.
        :type data.reserve_resources: boolean
        :arg data.sleep_time: Amount of time to pause (in seconds) between two syncs (default: 60)
        :type data.sleep_time: integer
        :arg data.enabled: Start the replication service immediately after first sync (default: true)
        :type data.enabled: boolean
        :arg data.bwlimit: Transfer rate limit in bytes (default: null => no limit)
        :type data.bwlimit: integer
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 406: Slave VM already exists
        :status 409: VM has pending tasks
        :status 423: Node is not operational / VM is not stopped or running / VM is not operational
        :status 424: Cannot import required image
        :status 428: VM definition has changed


    .. http:put:: /vm/(hostname_or_uuid)/replica/(repname)

        Update replication service parameters on target node.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg repname: **required** - Slave server identifier
        :type repname: string
        :arg data.reserve_resources: Whether to reserve resources (vCPU, RAM) on target compute node; \
**NOTE**: When disabled, the resources must be available (and will be reserved) before the \
:http:put:`failover action </vm/(hostname_or_uuid)/replica/(repname)/failover>`.
        :arg data.sleep_time: Amount of time to pause (in seconds) between two syncs
        :type data.sleep_time: integer
        :arg data.enabled: Pause or start the replication service
        :type data.enabled: boolean
        :arg data.bwlimit: Transfer rate limit in bytes
        :type data.bwlimit: integer
        :status 200: SUCCESS
        :status 205: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Slave VM not found
        :status 423: Node is not operational / VM is not operational
        :status 428: Reinitialization is required


    .. http:delete:: /vm/(hostname_or_uuid)/replica/(repname)

        Destroy slave VM and replication service on target node.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg repname: **required** - Slave server identifier
        :type repname: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Slave VM not found
        :status 423: Node is not operational / VM is not operational

    """
    return VmReplica(request, hostname_or_uuid, repname, data).response()


#: vm_status:   PUT: -
@api_view(('PUT',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vms() = IsVmOwner
@setting_required('VMS_VM_REPLICATION_ENABLED')
def vm_replica_failover(request, hostname_or_uuid, repname, data=None):
    """
    Fail over (:http:put:`PUT </vm/(hostname_or_uuid)/replica/(repname)/failover>`) to slave VM.

    .. http:put:: /vm/(hostname_or_uuid)/replica/(repname)/failover

        The slave VM will be promoted to a master VM and the current master VM will be stopped.
        The old master VM can be properly degraded to a slave VM by using \
:http:put:`PUT /vm/(hostname_or_uuid)/replica/(repname)/reinit </vm/(hostname_or_uuid)/replica/(repname)/reinit>`.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg repname: **required** - Slave server identifier
        :type repname: string
        :arg data.force: Perform failover even if VM has pending tasks (default: false)
        :type data.force: boolean
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Slave VM not found
        :status 409: VM has pending tasks
        :status 423: Node is not operational
        :status 428: Reinitialization is required / Not enough free resources on target node
    """
    return VmReplicaFailover(request, hostname_or_uuid, repname, data).put()


#: vm_status:   PUT: stopped, stopping, running
@api_view(('PUT',))
@request_data(permissions=(IsAdminOrReadOnly,))  # get_vms() = IsVmOwner
@setting_required('VMS_VM_REPLICATION_ENABLED')
def vm_replica_reinit(request, hostname_or_uuid, repname, data=None):
    """
    Reinitialize (:http:put:`PUT </vm/(hostname_or_uuid)/replica/(repname)/reinit>`) slave VM (former master VM).

    .. http:put:: /vm/(hostname_or_uuid)/replica/(repname)/reinit

        Degrade old master VM to slave VM and reinitialize/start replication after successful failover.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg repname: **required** - Slave server identifier
        :type repname: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found / Slave VM not found
        :status 423: Node is not operational / VM is not operational
        :status 428: Reinitialization is not required
    """
    return VmReplicaReinit(request, hostname_or_uuid, repname, data).put()
