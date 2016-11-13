from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsAnyDcUserAdminOrProfileOwner
from api.accounts.user.sshkey.api_views import UserSshkeyView

__all__ = ('sshkey_list', 'sshkey_manage',)


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsAnyDcUserAdminOrProfileOwner,))
def sshkey_list(request, username, data=None):
    """
    List (:http:get:`GET </accounts/user/(username)/sshkey>`) all user's SSH keys

    .. http:get:: /accounts/user/(username)/sshkey

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
        :arg data.full: Return list of all ssh keys with key details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``title`` (default: ``title``)
        :type data.order_by: string

        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: User not found
    """
    return UserSshkeyView(request, username, None, data, many=True).get()


@api_view(('GET', 'POST', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcUserAdminOrProfileOwner,))
def sshkey_manage(request, username, title, data=None):
    """
    Show (:http:get:`GET </accounts/user/(username)/sshkey/(title)>`),
    create (:http:post:`POST </accounts/user/(username)/sshkey/(title)>`) or
    delete (:http:delete:`DELETE </accounts/user/(username)/sshkey/(title)>`) a user's SSH key.

    .. http:get:: /accounts/user/(username)/sshkey/(title)

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
        :arg title: **required** - SSH key title
        :type title: string

        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: User not found

    .. http:post:: /accounts/user/(username)/sshkey/(title)

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
        :arg title: **required** - SSH key title
        :type title: string
        :arg data.key: **required** - Public SSH key in OpenSSH format
        :type data.key: string

        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: User not found
        :status 406: SSH key already exists

    .. http:delete:: /accounts/user/(username)/sshkey/(title)

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
        :arg title: **required** - SSH key title
        :type title: string

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: User not found / SSH key not found
    """
    return UserSshkeyView(request, username, title, data).response()
