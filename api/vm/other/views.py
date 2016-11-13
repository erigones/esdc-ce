from api.decorators import api_view, request_data
from api.vm.other.vm_screenshot import VmScreenshot

__all__ = ('vm_screenshot',)


#: vm_status:   GET:
#: vm_status:  POST: running, stopping
# noinspection PyUnusedLocal
@api_view(('GET', 'POST'))
@request_data()  # get_vm() = IsVmOwner
def vm_screenshot(request, hostname, data=None):
    """
    Create (:http:post:`POST </vm/(hostname)/screenshot>`) or
    display from cache (:http:get:`GET </vm/(hostname)/screenshot>`)
    a screenshot (base64 PNG format) of VM's console.

    .. http:get:: /vm/(hostname)/screenshot

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: VM not found
        :status 501: Operation not supported

    .. http:post:: /vm/(hostname)/screenshot

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |VmOwner|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Server hostname
        :type hostname: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 423: Node is not operational / VM is not operational
        :status 501: Operation not supported

    """
    return VmScreenshot(request, hostname, data).response()
