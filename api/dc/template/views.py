from api.decorators import api_view, request_data
from api.permissions import IsAdmin, IsSuperAdminOrReadOnly
from api.dc.template.api_views import DcTemplateView


__all__ = ('dc_template_list', 'dc_template')


@api_view(('GET',))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_template_list(request, data=None):
    """
    List (:http:get:`GET </dc/(dc)/template>`) available server templates in current datacenter.

    .. http:get:: /dc/(dc)/template

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg data.full: Return list of objects with all template details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found
    """
    return DcTemplateView(request, None, data).get(many=True)


# noinspection PyUnusedLocal
@api_view(('GET', 'POST', 'DELETE'))
@request_data(permissions=(IsAdmin, IsSuperAdminOrReadOnly))
def dc_template(request, name, data=None):
    """
    Show (:http:get:`GET </dc/(dc)/template/(name)>`),
    create (:http:post:`POST </dc/(dc)/template/(name)>`) or
    delete (:http:delete:`DELETE </dc/(dc)/template/(name)>`)
    a server template (name) association with a datacenter (dc).

    .. http:get:: /dc/(dc)/template/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |Admin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - Server template name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Template not found

    .. http:post:: /dc/(dc)/template/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - Server template name
        :type name: string
        :status 201: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Template not found
        :status 406: Template already exists

    .. http:delete:: /dc/(dc)/template/(name)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg request.dc: **required** - Datacenter name
        :type request.dc: string
        :arg name: **required** - Server template name
        :type name: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Datacenter not found / Template not found
        :status 428: Template is used by some VMs

    """
    return DcTemplateView(request, name, data).response()
