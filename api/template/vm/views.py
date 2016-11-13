from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsAnyDcTemplateAdmin
from api.template.vm.api_views import TemplateVmView

__all__ = ('template_vm_list',)


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsAnyDcTemplateAdmin,))
def template_vm_list(request, name, data=None):
    """
    List (:http:get:`GET </template/(name)/vm>`) all VMs, which are using a specific server template (name).

    .. http:get:: /template/(name)/vm

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |TemplateAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with all VM details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``hostname`` (default: ``hostname``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return TemplateVmView(request, name, data).get()
