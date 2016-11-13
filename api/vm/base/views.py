from api.decorators import api_view, request_data
from api.vm.base.vm_manage import VmManage

__all__ = ('vm_list', 'vm_manage')


#: vm_status:   GET:
# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data()  # get_vm() = IsVmOwner
def vm_list(request, data=None):
    """
    List (:http:get:`GET </vm>`) existing VMs.

    .. http:get:: /vm

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with some VM details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended VM details (default: false)
        :type data.extended: boolean
        :arg data.active: Display currently active (on compute node) VM details (default: false)
        :type data.active: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``hostname`` (default: ``hostname``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return VmManage(request, None, data).get(many=True)


#: vm_status:   GET:
#: vm_status:  POST: stopped, notcreated (recreate)
#: vm_status:   PUT: stopped, running
#: vm_status:DELETE: stopped, frozen
@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data()  # get_vm() = IsVmOwner + More security inside view
def vm_manage(request, hostname, data=None):
    """
    Get (:http:get:`GET </vm/(hostname)>`),
    create (deploy) (:http:post:`POST </vm/(hostname)>`),
    update (:http:put:`PUT </vm/(hostname)>`) or
    delete (:http:delete:`DELETE </vm/(hostname)>`)
    a VM on a compute node. The VM must be defined.

    .. http:get:: /vm/(hostname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg data.extended: Display extended VM details (default: false)
        :type data.extended: boolean
        :arg data.active: Display currently active (on compute node) VM details (default: false)
        :type data.active: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found

    .. http:post:: /vm/(hostname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner| `(recreate=true)`
            * |Admin| `(except recreate=true)`
        :Asynchronous?:
            * |async-yes| - Update on compute node, when VM definition has changed
            * |async-no| - Update in DB only, when VM definition was not changed
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :arg data.recreate: Delete and create the VM from scratch (default: false)
        :type data.recreate: boolean
        :arg data.force: Must be true to force recreate (default: false)
        :type data.force: boolean
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 409: VM has pending tasks
        :status 417: Are you sure? (recreate=true, force=false)
        :status 423: Node is not operational / VM is already created / VM is not stopped (recreate=true) / \
VM is locked or has slave VMs (recreate=true)
        :status 424: Cannot import required image
        :status 428: VM has no bootable disk / Could not find node with free resources / \
VM owner has no SSH keys available

    .. http:put:: /vm/(hostname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 409: VM has pending tasks
        :status 417: VM has snapshots (disk size update)
        :status 423: Node is not operational / VM is not stopped or running / VM is locked or has slave VMs
        :status 424: Cannot import required image
        :status 428: VM has to be stopped when updating disks or NICs

    .. http:delete:: /vm/(hostname)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 409: VM has pending tasks
        :status 423: Node is not operational / VM is not stopped / VM is locked or has slave VMs

    """
    return VmManage(request, hostname, data).response()
