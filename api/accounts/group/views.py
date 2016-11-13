from api.decorators import api_view, request_data_defaultdc, setting_required
from api.permissions import IsAnyDcUserAdmin, IsSuperAdminOrReadOnly
from api.accounts.group.api_views import GroupView

__all__ = ('group_list', 'group_manage')

#
# NOTE: GET methods for these views are available to UserAdmins and POST/PUT/DELETE methods
# are only available to SuperAdmins. Otherwise the UserAdmin could easily give himself SuperAdmin privileges.
#


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsAnyDcUserAdmin,))
@setting_required('ACL_ENABLED')
def group_list(request, data=None):
    """
    List (:http:get:`GET </accounts/group>`) all available groups.

    .. http:get:: /accounts/group

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |UserAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of all groups with group details (default: false)
        :type data.full: boolean
        :arg data.extended: Display extended group details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name`` (default: ``name``)
        :type data.order_by: string

        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return GroupView(request, None, data, many=True).get()


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcUserAdmin, IsSuperAdminOrReadOnly))
@setting_required('ACL_ENABLED')
def group_manage(request, name, data=None):
    """
    Show (:http:get:`GET </accounts/group/(name)>`), create (:http:post:`POST </accounts/group/(name)>`),
    update (:http:put:`PUT </accounts/group/(name)>`) or delete (:http:delete:`DELETE </accounts/group/(name)>`)
    details of a group.

    .. http:get:: /accounts/group/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |UserAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Group name
        :type name: string
        :arg data.extended: Display extended group details (default: false)
        :type data.extended: boolean

        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Group not found

    .. http:post:: /accounts/group/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Group name
        :type name: string
        :arg data.alias: Short group name alias (default: ``name``)
        :type data.alias: string
        :arg data.permissions: List of permission names assigned to the group (supports multiple permissions, \
requires :http:get:`valid permissions </accounts/permission/(name)>`, default: [])
        :type data.permissions: array
        :arg data.users: Username assigned to the group (supports multiple users, \
requires :http:get:`valid users </accounts/user/(username)>`, default: [])
        :type data.users: array
        :arg data.dc_bound: Whether the group is bound to a datacenter (requires |SuperAdmin| permission) \
(default: true)
        :type data.dc_bound: boolean
        :arg data.dc: Name of the datacenter the group will be attached to (**required** if DC-bound)
        :type data.dc: string

        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found
        :status 406: Group already exists

    .. http:put:: /accounts/group/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Group name
        :type name: string
        :arg data.alias: Short group name alias (default: ``name``)
        :type data.alias: string
        :arg data.permissions: List of permission names assigned to the group (supports multiple permissions, \
overwrites all already assigned permissions, requires :http:get:`valid permissions </accounts/permission/(name)>`)
        :type data.permissions: array
        :arg data.users: Username assigned to the group (supports multiple users, overwrites all already assigned \
users, requires :http:get:`valid users </accounts/user/(username)>`)
        :type data.users: array
        :arg data.dc_bound: Whether the group is bound to a datacenter (requires |SuperAdmin| permission)
        :type data.dc_bound: boolean

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Group not found

    .. http:delete:: /accounts/group/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Group name
        :type name: string

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Group not found
    """
    return GroupView(request, name, data).response()
