from socketio import socketio_manage
from django.http import HttpResponse
from django.db import close_old_connections
from django.core.exceptions import PermissionDenied

from sio.namespaces import APINamespace

from logging import getLogger, DEBUG, INFO, ERROR, WARNING
logger = getLogger(__name__)

logger.critical("SOM TU #000000!")
def socketio(request):
    """
    Starting socket.io connection here.
    """
    if request.user.is_authenticated:
        if 'socketio' in request.environ:
            socketio_manage(request.environ, namespaces={'': APINamespace}, request=request)
            try:
                return HttpResponse()
            finally:
                close_old_connections()
        else:
            return HttpResponse(status=204)
    else:
        raise PermissionDenied
