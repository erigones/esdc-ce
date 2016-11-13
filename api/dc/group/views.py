from api.decorators import api_view, request_data
from api.permissions import IsAdmin, IsSuperAdminOrReadOnly
from api.dc.group.api_views import DcGroupView

__all__ = ('dc_group_list', 'dc_group')


@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_group_list(request, data=None):
    """
    List (:http:get:`GET </dc/(dc)/group>`) groups available in current datacenter (dc).

    .. http:get:: /dc/(dc)/group

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg data.full: Return list of objects with all group details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found
    """
    return DcGroupView(request, None, data).get(many=True)


# noinspection PyUnusedLocal
@api_view(('GET', 'POST', 'DELETE'))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_group(request, name, data=None):
    """
    Show (:http:get:`GET </dc/(dc)/group/(name)>`),
    create (:http:post:`POST </dc/(dc)/group/(name)>`) or
    delete (:http:delete:`DELETE </dc/(dc)/group/(name)>`)
    a group (name) association with a datacenter (dc).

    .. http:get:: /dc/(dc)/group/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg request.name: **required** - Group name
        :type request.name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Group not found

    .. http:post:: /dc/(dc)/group/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg request.name: **required** - Group name
        :type request.name: string

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found / Group not found
        :status 406: Group already exists

    .. http:delete:: /dc/(dc)/group/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg request.name: **required** - Group name
        :type request.name: string

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Datacenter not found / Group not found
    """
    return DcGroupView(request, name, data).response()
