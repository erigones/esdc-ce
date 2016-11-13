from api.decorators import request_data_defaultdc, api_view
from api.permissions import IsSuperAdmin
from api.node.sysinfo.api_views import NodeSysinfoView

__all__ = ('node_sysinfo',)


@api_view(('PUT',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def node_sysinfo(request, hostname, data=None):
    """
    Updates (:http:put:`PUT </node/(hostname)/sysinfo>`) compute node's system information by running the esysinfo
    command on the compute node.

    .. http:put:: /node/(hostname)/sysinfo

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-yes|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found
        :status 423: Node not operational
    """
    return NodeSysinfoView(request, hostname, data).put()
