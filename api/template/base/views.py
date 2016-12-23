from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsAnyDcTemplateAdmin
from api.template.base.api_views import TemplateView

__all__ = ('template_list', 'template_manage')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsAnyDcTemplateAdmin,))
def template_list(request, data=None):
    """
    List (:http:get:`GET </template>`) all server templates.

    .. http:get:: /template

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |TemplateAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with all server template details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended server template details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``created`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return TemplateView(request, None, data).get(many=True)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcTemplateAdmin,))
def template_manage(request, name, data=None):
    """
    Show (:http:get:`GET </template/(name)>`), create (:http:post:`POST </template/(name)>`)
    update (:http:put:`PUT </template/(name)>`) or delete (:http:delete:`DELETE </template/(name)>`)
    a server template.

    .. warning:: EXPERIMENTAL API function.

    .. http:get:: /template/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |TemplateAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Server template name
        :type name: string
        :arg data.extended: Display extended server template details (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Template not found

    .. http:post:: /template/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |TemplateAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Server template name
        :type name: string
        :arg data.alias: Short server template name (default: ``name``)
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private, 4 - Deleted) (default: 3)
        :type data.access: integer
        :arg data.owner: User that owns the server template (default: logged in user)
        :type data.owner: string
        :arg data.desc: Template image description
        :type data.desc: string
        :arg data.ostype: Operating system type (null - all OS types, 1 - Linux, 2 - SunOS, 3 - BSD, 4 - Windows, \
5 - SunOS Zone, 6 - Linux Zone) (default: null)
        :type data.ostype: integer
        :arg data.dc_bound: Whether the server template is bound to a datacenter (requires |SuperAdmin| permission) \
(default: true)
        :type data.dc_bound: boolean
        :arg data.dc: Name of the datacenter the server template will be attached to (**required** if DC-bound)
        :type data.dc: string
        :arg data.vm_define: :http:get:`Server definition object </vm/(hostname_or_uuid)/define>` (default: {})
        :type data.vm_define: object
        :arg data.vm_define_disk: List of \
:http:get:`server disk definition objects </vm/(hostname_or_uuid)/define/disk/(disk_id)>` (default: [])
        :type data.vm_define_disk: array
        :arg data.vm_define_nic: List of \
:http:get:`server NIC definition objects </vm/(hostname_or_uuid)/define/nic/(nic_id)>` (default: [])
        :type data.vm_define_nic: array
        :arg data.vm_define_snapshot: List of \
:http:get:`server snapshot definition objects </vm/(hostname_or_uuid)/define/snapshot/(snapdef)>` (default: [])
        :type data.vm_define_snapshot: array
        :arg data.vm_define_backup: List of \
:http:get:`server backup definition objects </vm/(hostname_or_uuid)/define/backup/(bkpdef)>` (default: [])
        :type data.vm_define_backup: array
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found
        :status 406: Template already exists

    .. http:put:: /template/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |TemplateAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Server template name
        :type name: string
        :arg data.alias: Short server template name
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private, 4 - Deleted)
        :type data.access: integer
        :arg data.owner: User that owns the server template
        :type data.owner: string
        :arg data.desc: Template image description
        :type data.desc: string
        :arg data.ostype: Operating system type (null - all OS types, 1 - Linux, 2 - SunOS, 3 - BSD, 4 - Windows, \
5 - SunOS Zone, 6 - Linux Zone)
        :type data.ostype: integer
        :arg data.dc_bound: Whether the server template is bound to a datacenter (requires |SuperAdmin| permission)
        :type data.dc_bound: boolean
        :arg data.vm_define: :http:get:`Server definition object </vm/(hostname_or_uuid)/define>`
        :type data.vm_define: object
        :arg data.vm_define_disk: List of \
:http:get:`server disk definition objects </vm/(hostname_or_uuid)/define/disk/(disk_id)>`
        :type data.vm_define_disk: array
        :arg data.vm_define_nic: List of \
:http:get:`server NIC definition objects </vm/(hostname_or_uuid)/define/nic/(nic_id)>`
        :type data.vm_define_nic: array
        :arg data.vm_define_snapshot: List of \
:http:get:`server snapshot definition objects </vm/(hostname_or_uuid)/define/snapshot/(snapdef)>`
        :type data.vm_define_snapshot: array
        :arg data.vm_define_backup: List of \
:http:get:`server backup definition objects </vm/(hostname_or_uuid)/define/backup/(bkpdef)>`
        :type data.vm_define_backup: array
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Template not found

    .. http:delete:: /template/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |TemplateAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Server template name
        :type name: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Template not found
        :status 428: Template is used by some VMs

    """
    return TemplateView(request, name, data).response()
