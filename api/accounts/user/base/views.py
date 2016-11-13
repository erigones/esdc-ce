from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsAnyDcUserAdmin, IsProfileOwner, IsAnyDcUserAdminOrProfileOwner
from api.accounts.user.base.api_views import UserView
from api.accounts.user.profile.api_views import UserProfileView


__all__ = ('user_list', 'user_manage', 'user_apikeys', 'userprofile_list')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsAnyDcUserAdmin,))
def user_list(request, data=None):
    """
    List (:http:get:`GET </accounts/user>`) all available users.

    .. http:get:: /accounts/user

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |UserAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of all users with user details (default: false)
        :type data.full: boolean
        :arg data.extended: Display extended user details (default: false)
        :type data.extended: boolean
        :arg data.is_active: Return list of all active users (default: true)
        :type data.is_active: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``username``, ``created`` \
(default: ``username``)
        :type data.order_by: string

        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return UserView(request, None, data, many=True).get()


@api_view(('GET', 'PUT', 'POST', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcUserAdminOrProfileOwner,))
def user_manage(request, username, data=None):
    """
    Show (:http:get:`GET </accounts/user/(username)>`), create (:http:post:`POST </accounts/user/(username)>`),
    update (:http:put:`PUT </accounts/user/(username)>`) or delete (:http:delete:`DELETE </accounts/user/(username)>`)
    a user.

    .. http:get:: /accounts/user/(username)

        .. note:: For security reasons, api-key and callback-key values are not displayed. \
To see their values use :http:get:`GET /accounts/user/(username)/apikeys </accounts/user/(username)/apikeys>`

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |ProfileOwner|
            * |UserAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg username: **required** - Username
        :type username: string
        :arg data.extended: Display extended user details (default: false)
        :type data.extended: boolean

        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: User not found

    .. http:post:: /accounts/user/(username)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |UserAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg username: **required** - Username
        :type username: string
        :arg data.first_name: **required** - User's first name
        :type data.first_name: string
        :arg data.last_name: **required** - User's last name
        :type data.last_name: string
        :arg data.email: **required** - User's primary email (valid email address)
        :type data.email: string
        :arg data.password: **required** - User's password
        :type data.password: string
        :arg data.groups: User roles (supports multiple groups, \
requires :http:get:`valid group </accounts/group/(name)>`, \
requires |SuperAdmin| permission for ``dc_bound=false``, and |UserAdmin| permission for ``dc_bound=true``, but \
only ``dc_bound=true`` roles can be assigned) (default: [])
        :type data.groups: array
        :arg data.dc_bound: Whether the user is bound to a datacenter (requires |SuperAdmin| permission) \
(default: None)
        :type data.dc_bound: boolean
        :arg data.dc: Name of the datacenter the user will be attached to (**required** if DC-bound)
        :type data.dc: string
        :arg data.api_access: Allow the user to access the API via HTTP (requires |SuperAdmin| permission for \
``dc_bound=false``, and |UserAdmin| permission for ``dc_bound=true``) (default: false)
        :type data.api_access: boolean
        :arg data.api_key: Generate new API key value (default: false)
        :type data.api_key: boolean
        :arg data.callback_key: Generate new callback key value (default: false)
        :type data.callback_key: boolean
        :arg data.is_active: Allow the user to login to the application (requires |SuperAdmin| permission for \
``dc_bound=false``, and |UserAdmin| permission for ``dc_bound=true``) (default: true)
        :type data.is_active: boolean
        :arg data.is_super_admin: Grant SuperAdmin rights to the user (requires |SuperAdmin| permission) \
(default: false)
        :type data.is_super_admin: boolean

        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found
        :status 406: User already exists

    .. http:put:: /accounts/user/(username)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |ProfileOwner|
            * |UserAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg username: **required** - Username
        :type username: string
        :arg data.first_name: User first name
        :type data.first_name: string
        :arg data.last_name: User last name
        :type data.last_name: string
        :arg data.email: Primary user email (valid email address)
        :type data.email: string
        :arg data.password: User password
        :type data.password: string
        :arg data.groups: User groups (supports multiple groups, overwrite all already assigned groups, \
requires :http:get:`valid group </accounts/group/(name)>`, requires |SuperAdmin| permission for \
``dc_bound=false``, and |UserAdmin| permission for ``dc_bound=true``, but only ``dc_bound=true`` roles can be assigned)
        :type data.groups: array
        :arg data.dc_bound: Whether the user is bound to a datacenter (requires |SuperAdmin| permission)
        :type data.dc_bound: boolean
        :arg data.dc: Name of the datacenter the user will be attached to (**required** if DC-bound)
        :type data.dc: string
        :arg data.api_access: Allow the user to access the API via HTTP (requires |SuperAdmin| permission for \
``dc_bound=false``, and |UserAdmin| permission for ``dc_bound=true``)
        :type data.api_access: boolean
        :arg data.api_key: Generate new API key value
        :type data.api_key: boolean
        :arg data.callback_key: Generate new callback key value
        :type data.callback_key: boolean
        :arg data.is_active: Allow the user to login to the application (requires |SuperAdmin| permission for \
``dc_bound=false``, and |UserAdmin| permission for ``dc_bound=true``)
        :type data.is_active: boolean
        :arg data.is_super_admin: Grant SuperAdmin rights to the user (requires |SuperAdmin| permission)
        :type data.is_super_admin: boolean

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: User not found / Datacenter not found

    .. http:delete:: /accounts/user/(username)

        .. note:: A user can be deleted only if he has no relations to any other objects.

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |UserAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg username: **required** - Username
        :type username: string

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: User not found
    """
    return UserView(request, username, data).response()


@api_view(('GET', 'PUT'))
@request_data_defaultdc(permissions=(IsProfileOwner,))
def user_apikeys(request, username, data=None):
    """
    Show (:http:get:`GET </accounts/user/(username)/apikeys>`),
    update (:http:put:`PUT </accounts/user/(username)/apikeys>`) a user API key and Callback key.

    .. note:: This function is available only when user is logged in via username and password. \
Authenticated requests with ``ES-API-KEY`` header are forbidden.

    .. http:get:: /accounts/user/(username)/apikeys

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |ProfileOwner|
        :Asynchronous?:
            * |async-no|
        :arg username: **required** - Username
        :type username: string

        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: User not found

    .. http:put:: /accounts/user/(username)/apikeys

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |ProfileOwner|
        :Asynchronous?:
            * |async-no|
        :arg username: **required** - Username
        :type username: string
        :arg data.api_key: Generate new API key value (default: false)
        :type data.api_key: boolean
        :arg data.callback_key: Generate new callback key value (default: false)
        :type data.callback_key: boolean

        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: User not found
    """
    return UserView(request, username, data).api_key()


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsAnyDcUserAdmin,))
def userprofile_list(request, data=None):
    """
    List (:http:get:`GET </accounts/user/profile>`) all available user profiles.

    .. http:get:: /accounts/user/profile

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |UserAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``username``, ``created`` \
(default: ``username``)
        :type data.order_by: string

        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return UserProfileView(request, None, data, many=True).get()
