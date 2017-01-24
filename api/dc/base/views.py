from api.decorators import api_view, request_data_nodc
from api.permissions import IsSuperAdmin, IsSuperAdminOrReadOnly
from api.dc.base.dc_view import DcView
from api.dc.base.dc_settings import DcSettingsView

__all__ = ('dc_list', 'dc_manage', 'dc_settings')


@api_view(('GET',))
@request_data_nodc(permissions=(IsSuperAdminOrReadOnly,))
def dc_list(request, data=None):
    """
    List (:http:get:`GET </dc>`) available Datacenters.

    .. http:get:: /dc

        :DC-bound?:
            * |dc-yes|
        :Permissions:
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with all DC details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended DC details \
(default: false, requires |SuperAdmin| permission)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``created`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return DcView(request, None, data).get(many=True)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data_nodc(permissions=(IsSuperAdminOrReadOnly,))
def dc_manage(request, dc, data=None):
    """
    Show (:http:get:`GET </dc/(dc)>`), create (:http:post:`POST </dc/(dc)>`),
    change (:http:put:`PUT </dc/(dc)>`) or delete (:http:delete:`DELETE </dc/(dc)>`) a virtual datacenter.

    .. http:get:: /dc/(dc)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
        :Asynchronous?:
            * |async-no|
        :arg dc: **required** - Datacenter name
        :type dc: string
        :arg data.extended: Display extended DC details (default: false, requires |SuperAdmin| permission)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found

    .. http:post:: /dc/(dc)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg dc: **required** - Datacenter name
        :type dc: string
        :arg data.site: **required** - Datacenter web site hostname
        :type data.site: string
        :arg data.alias: Short datacenter name (default: ``name``)
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private) (default: 3)
        :type data.access: integer
        :arg data.owner: User that owns the Datacenter (default: logged in user)
        :type data.owner: string
        :arg data.groups: List of user groups (default: [])
        :type data.groups: array
        :arg data.desc: Datacenter description
        :type data.desc: string
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 406: Datacenter already exists

    .. http:put:: /dc/(dc)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg dc: **required** - Datacenter name
        :type dc: string
        :arg data.site: Datacenter web site hostname
        :type data.site: string
        :arg data.alias: Short datacenter name
        :type data.alias: string
        :arg data.access: Access type (1 - Public, 3 - Private)
        :type data.access: integer
        :arg data.owner: User that owns the Datacenter
        :type data.owner: string
        :arg data.groups: List of user groups
        :type data.groups: array
        :arg data.desc: Datacenter description
        :type data.desc: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found

    .. http:delete:: /dc/(dc)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg dc: **required** - Datacenter name
        :type dc: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found
        :status 428: Datacenter has nodes / Datacenter has VMs / Default datacenter cannot be deleted

    """
    return DcView(request, dc, data).response()


@api_view(('GET', 'PUT'))
@request_data_nodc(permissions=(IsSuperAdmin,))
def dc_settings(request, dc, data=None):
    """
    Show (:http:get:`GET </dc/(dc)/settings>`) or update (:http:put:`PUT </dc/(dc)/settings>`)
    settings of a virtual datacenter.

    .. note:: Global settings can only be changed from the main data center.

    .. http:get:: /dc/(dc)/settings

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg dc: **required** - Datacenter name
        :type dc: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found

    .. http:put:: /dc/(dc)/settings

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg dc: **required** - Datacenter name
        :type dc: string
        :arg data.<setting_name>: See example below for current list of settings and \
consult the user guide for more information
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found

    """
    return DcSettingsView(request, dc, data).response()
