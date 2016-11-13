from api.decorators import api_view, request_data, setting_required
from api.permissions import IsAdmin, IsSuperAdminOrReadOnly
from api.dc.domain.api_views import DcDomainView

__all__ = ('dc_domain_list', 'dc_domain')


@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
@setting_required('DNS_ENABLED')
def dc_domain_list(request, data=None):
    """
    List (:http:get:`GET </dc/(dc)/domain>`) available DNS domains in current datacenter.

    .. http:get:: /dc/(dc)/domain

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg data.full: Return list of objects with all DNS domain details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found
    """
    return DcDomainView(request, None, data).get(many=True)


# noinspection PyUnusedLocal
@api_view(('GET', 'POST', 'DELETE'))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
@setting_required('DNS_ENABLED')
def dc_domain(request, name, data=None):
    """
    Show (:http:get:`GET </dc/(dc)/domain/(name)>`),
    create (:http:post:`POST </dc/(dc)/domain/(name)>`) or
    delete (:http:delete:`DELETE </dc/(dc)/domain/(name)>`)
    a DNS domain (name) association with a datacenter (dc).

    .. http:get:: /dc/(dc)/domain/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - DNS domain name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Domain not found

    .. http:post:: /dc/(dc)/domain/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - DNS domain name
        :type name: string
        :status 201: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Domain not found
        :status 406: Domain already exists

    .. http:delete:: /dc/(dc)/domain/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - DNS domain name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Domain not found
        :status 417: Default VM domain cannot be removed from datacenter

    """
    return DcDomainView(request, name, data).response()
