from api.decorators import api_view, request_data
from api.vm.status.vm_status import VmStatus

__all__ = ('vm_status', 'vm_status_list')


#: vm_status:   GET:
# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data()  # get_vm() = IsVmOwner
def vm_status_list(request, data=None):
    """
    List (:http:get:`GET </vm/status>`) VMs with their current status.

    .. http:get:: /vm/status

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``hostname`` (default: ``hostname``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return VmStatus(request, None, None, data).get(many=True)


#: vm_status:   GET:
#: vm_status:   PUT + current=true: all expect frozen
#: vm_status:   PUT: running, stopped, stopping, frozen
@api_view(('GET', 'PUT'))
@request_data()  # get_vm() = IsVmOwner
def vm_status(request, hostname_or_uuid, action=None, data=None):
    """
    Get (:http:get:`GET </vm/(hostname_or_uuid)/status>`) or
    set (:http:put:`PUT </vm/(hostname_or_uuid)/status/start>`) VM status by using
    :http:put:`start </vm/(hostname_or_uuid)/status/start>`,
    :http:put:`stop </vm/(hostname_or_uuid)/status/stop>` or
    :http:put:`reboot </vm/(hostname_or_uuid)/status/reboot>` action.

    .. http:get:: /vm/(hostname_or_uuid)/status

        Retrieves current status from database.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 423: Node is not operational / VM is not operational

    .. http:get:: /vm/(hostname_or_uuid)/status/current

        Retrieves current VM status from compute node.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 423: Node is not operational / VM is not operational

    .. http:put:: /vm/(hostname_or_uuid)/status/current

        Retrieves current VM status from compute node and updates status value in DB for the VM.

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 409: VM has pending tasks
        :status 423: Node is not operational / VM is not operational

    .. http:put:: /vm/(hostname_or_uuid)/status/start

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.update: Update VM configuration (if changed) on compute node (default: true)
        :type data.update: boolean
        :arg data.cdimage: Name of the primary ISO image to boot from (default: null)
        :type data.cdimage: string
        :arg data.cdimage_once: Boot only once from the primary ISO image (default: true)
        :type data.cdimage_once: boolean
        :arg data.cdimage2: Name of the secondary ISO image to boot from. Can be only used along with `cdimage` \
(default: null)
        :type data.cdimage2: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 409: VM has pending tasks (`update=true`)
        :status 417: Bad action
        :status 423: Node is not operational / VM is not operational
        :status 428: VM must be updated first / VM is not installed

    .. http:put:: /vm/(hostname_or_uuid)/status/stop

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
            * |Admin| `(only for freeze=true or unfreeze=true)`
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.force: Force change of the status (default: false)
        :type data.force: boolean
        :arg data.update: Update VM configuration (if changed) after stopping \
VM on compute node (default: false)
        :type data.update: boolean
        :arg data.timeout: Time period (in seconds) for a graceful shutdown, after which the force shutdown \
is send to the VM (KVM only) (default: 180 seconds / 300 seconds for Windows VM)
        :type data.timeout: integer
        :arg data.freeze: Set frozen status after successful stop action (default: false)
        :type data.freeze: boolean
        :arg data.unfreeze: Remove frozen status and set it back to stopped (default: false)
        :type data.unfreeze: boolean
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 409: VM has pending tasks (`update=true`)
        :status 417: Bad action / VM has snapshots (disk size update)
        :status 423: Node is not operational / VM is not operational / VM is already stopping
        :status 428: Cannot perform update while VM is stopping

    .. http:put:: /vm/(hostname_or_uuid)/status/reboot

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.force: Force change of the status (default: false)
        :type data.force: boolean
        :arg data.update: Update VM configuration (if changed) before starting (after stop) \
VM on compute node (default: true)
        :type data.update: boolean
        :arg data.timeout: Time period (in seconds) for a graceful reboot, after which the force reboot \
is send to the VM (KVM only) (default: 180 seconds / 300 seconds for Windows VM)
        :type data.timeout: integer
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 409: VM has pending tasks (`update=true`)
        :status 417: Bad action / VM has snapshots (disk size update)
        :status 423: Node is not operational / VM is not operational / VM is already stopping
        :status 428: Cannot perform update while VM is stopping

    """
    return VmStatus(request, hostname_or_uuid, action, data).response()
