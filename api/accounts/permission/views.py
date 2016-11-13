from api.decorators import api_view, request_data_defaultdc, setting_required
from api.permissions import IsSuperAdmin
from api.accounts.permission.api_views import PermissionView

__all__ = ('permission_list', 'permission_manage')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
@setting_required('ACL_ENABLED')
def permission_list(request, data=None):
    """
    List (:http:get:`GET </accounts/permission>`) all available permissions.

    .. http:get:: /accounts/permission

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of all permissions with permission details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name`` (default: ``name``)
        :type data.order_by: string

        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return PermissionView(request, None, data, many=True).get()


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
@setting_required('ACL_ENABLED')
def permission_manage(request, name, data=None):
    """
    Show (:http:get:`GET </accounts/permission/(name)>`) details of a permission.

    Adding, editing or deleting pre-defined permissions is not allowed.

    .. http:get:: /accounts/permission/(name)

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Permission name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Permission not found
    """
    return PermissionView(request, name, data).response()
