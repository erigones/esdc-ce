from api.decorators import api_view, request_data
from api.permissions import IsAdmin, IsSuperAdminOrReadOnly
from api.dc.user.api_views import DcUserView

__all__ = ('dc_user_list', 'dc_user')


@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_user_list(request, data=None):
    """
    List (:http:get:`GET </dc/(dc)/user>`) users available in current datacenter (dc).

    .. http:get:: /dc/(dc)/user

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg data.full: Return list of objects with all user details (default: false)
        :type data.full: boolean
        :arg data.active: Return list of users that are active (default: true)
        :type data.active: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``username`` (default: ``username``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found
    """
    return DcUserView(request, None, data).get(many=True)


# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_user(request, username, data=None):
    """
    Show (:http:get:`GET </dc/(dc)/user/(username)>`) details of a user (username)
    with access to a specific datacenter (dc).

    .. http:get:: /dc/(dc)/user/(username)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg username: **required** - Username
        :type username: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / User not found
    """
    return DcUserView(request, username, data).response()
