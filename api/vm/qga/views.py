from api.decorators import api_view, request_data
from api.vm.qga.api_views import VmQGA

__all__ = ('vm_qga',)


#: vm_status:  PUT: running, stopping
@api_view(('PUT',))
@request_data()  # get_vm() = IsVmOwner
def vm_qga(request, hostname_or_uuid, command, data=None):
    """
    Run (:http:put:`PUT </vm/(hostname_or_uuid)/qga/(command)>`) a command via Qemu Guest Agent.

    .. http:put:: /vm/(hostname_or_uuid)/qga/(command)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg command: **required** - QGA command. Available commands are:

            * ``fsfreeze`` ``<status|freeze|thaw>``
            * ``info``
            * ``ping``
            * ``sync``
            * ``reboot``
            * ``poweroff``
            * ``get-time``
            * ``set-time`` ``[epoch time in nanoseconds]``

        :type command: string
        :arg data.params: List of command parameters
        :type data.params: array
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 412: Invalid command
        :status 423: Node is not operational / VM is not operational
        :status 501: Operation not supported

    """
    return VmQGA(request, hostname_or_uuid, command, data).put()
