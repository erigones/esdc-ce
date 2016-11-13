import socket

from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsSuperAdmin
from api.task.response import SuccessTaskResponse
from api.system.base.api_views import SystemLogsView

__all__ = ('system_version', 'system_logs')


# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_version(request, data=None):
    """
    Show (:http:get:`GET </system/version>`) Danube Cloud version.

    .. http:get:: /system/version

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    from core.version import __version__
    return SuccessTaskResponse(request, {'hostname': socket.gethostname(), 'version': __version__}, dc_bound=False)


# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdmin,))
def system_logs(request, data=None):
    """
    Retrieve (:http:get:`GET </system/logs>`) Danube Cloud log files.

    .. http:get:: /system/logs

        In case of a success, the response contains an object with log names as keys and contents of \
log files as values. If the file does not exist the object values will be ``null``.

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.logname: Name of the specific log file to be retrieved
        :type data.logname: string
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: ``logname`` not found
    """
    return SystemLogsView(request, data).get()
