from api.permissions import IsAdmin, IsSuperAdmin
from api.decorators import api_view, request_data
from api.vm.migrate.vm_migrate import VmMigrate
from api.vm.migrate.vm_dc import VmDc

__all__ = ('vm_migrate', 'vm_dc')


#: vm_status:   PUT: stopped, running
@api_view(('PUT',))
@request_data(permissions=(IsAdmin,))
def vm_migrate(request, hostname_or_uuid, data=None):
    """
    Migrate (:http:put:`PUT </vm/(hostname_or_uuid)/migrate>`) server to another compute node and/or disks to another storage.

    .. note:: A dummy (DB only) slave server is created during the migration process to reserve the same amount of \
resources on target compute node in server's datacenter.

    .. http:put:: /vm/(hostname_or_uuid)/migrate

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.node: Target compute node hostname
        :type data.node: string
        :arg data.root_zpool: New zpool for the VM zone or OS zone including data disk
        :type data.root_zpool: string
        :arg data.disk_zpools: New zpools for VM's disks (``{disk_id: zpool}``)
        :type data.disk_zpools: object
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 409: VM has pending tasks
        :status 423: Node is not operational / VM is not stopped or running / VM is locked or has slave VMs
        :status 424: Cannot import required image
        :status 428: VM definition has changed

    """
    return VmMigrate(request, hostname_or_uuid, data).put()


#: vm_status:   PUT: stopped, running, undefined
@api_view(('PUT',))
@request_data(permissions=(IsSuperAdmin,))
def vm_dc(request, hostname_or_uuid, data=None):
    """
    Migrate (:http:put:`PUT </vm/(hostname_or_uuid)/migrate/dc>`) server to another datacenter.

    .. warning:: EXPERIMENTAL API function.

    .. http:put:: /vm/(hostname_or_uuid)/migrate/dc

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname_or_uuid: **required** - Server hostname or uuid
        :type hostname_or_uuid: string
        :arg data.target_dc: Target datacenter
        :type data.target_dc: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: VM not found
        :status 409: VM has pending tasks
        :status 423: Node is not operational / VM is not stopped, running or notcreated / VM is locked or has slave VMs
        :status 428: VM definition has changed

    """
    return VmDc(request, hostname_or_uuid, data).put()
