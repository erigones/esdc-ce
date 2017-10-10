from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.system.node.api_views import NodeVersionView, NodeServiceStatusView, NodeUpdateView, NodeLogsView

__all__ = (
    'system_node_version_list',
    'system_node_version',
    'system_node_service_status_list',
    'system_node_service_status',
    'system_node_update',
    'system_node_logs',
)


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_node_version_list(request, data=None):
    """
    Show (:http:get:`GET </system/node/version>`) Danube Cloud version for all compute nodes.

    .. http:get:: /system/node/version

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return NodeVersionView(request, None, data).get(many=True)


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_node_version(request, hostname, data=None):
    """
    Show (:http:get:`GET </system/node/(hostname)/version>`) Danube Cloud compute node version.

    .. http:get:: /system/node/(hostname)/version

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Node not found
    """
    return NodeVersionView(request, hostname, data).get()


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_node_service_status_list(request, hostname, data=None):
    """
    Get (:http:get:`GET </system/node/(hostname)/service/status>`) status of all system services on a compute node.

    .. http:get:: /system/node/(hostname)/service/status

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found
        :status 504: Node worker is not responding
    """
    return NodeServiceStatusView(request, hostname, None, data).get()


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_node_service_status(request, hostname, name, data=None):
    """
    Get (:http:get:`GET </system/node/(hostname)/service/(name)/status>`) service status on a compute node.

    .. http:get:: /system/node/(hostname)/service/(name)/status

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg name: **required** - Service name
        :type name: string
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found / Service not found
        :status 504: Node worker is not responding
    """
    return NodeServiceStatusView(request, hostname, name, data).response()


@api_view(('PUT',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_node_update(request, hostname, data=None):
    """
    Install (:http:put:`PUT </system/node/(hostname)/update>`) Danube Cloud update on a compute node.

    .. http:put:: /system/node/(hostname)/update

        .. note:: The compute node software will be updated to the \
same :http:get:`version </system/version>` as installed on the main Danube Cloud management VM. \
Use this API call after successful :http:put:`system update </system/update>`.

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg data.version: **required** - git tag (e.g. ``v2.6.5``) or git commit to which the system should be updated
        :type data.version: string
        :arg data.key: X509 private key file used for authentication against EE git server. \
Please note that file MUST contain standard x509 file BEGIN/END header/footer. \
If not present, cached key file "update.key" will be used.
        :type data.key: string
        :arg data.cert: X509 private cert file used for authentication against EE git server \
Please note that file MUST contain standard x509 file BEGIN/END headers/footer. \
If not present, cached cert file "update.crt" will be used.
        :type data.cert: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Node not found
        :status 417: Node update file is not available
        :status 423: Node is not in maintenance state / Node version information could not be retrieved / \
Task is already running
        :status 428: Node is already up-to-date
        :status 504: Node worker is not responding
    """
    return NodeUpdateView(request, hostname, data).put()


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_node_logs(request, hostname, data=None):
    """
    Retrieve (:http:get:`GET </system/node/(hostname)/logs>`) Danube Cloud log files from compute node.

    .. http:get:: /system/node/(hostname)/logs

        In case of a success, the response contains an object with log names as keys and contents of \
log files (limited to last 10 kB) as values. If the file does not exist the object values will be ``null``.

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg hostname: **required** - Node hostname
        :type hostname: string
        :arg data.logname: Name of the specific log file to be retrieved
        :type data.logname: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Node not found / ``logname`` not found
        :status 423: Node is not operational
        :status 504: Node worker is not responding
    """
    return NodeLogsView(request, hostname, data).get()
