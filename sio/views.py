from socketio import socketio_manage
from django.http import HttpResponse, HttpResponseForbidden
from django.db import close_old_connections

from sio.namespaces import APINamespace


def socketio(request):
    """
    Starting socket.io connection here.
    """
    if request.user.is_authenticated():
        if 'socketio' in request.environ:
            socketio_manage(request.environ, namespaces={'': APINamespace}, request=request)
            try:
                return HttpResponse(None)
            finally:
                close_old_connections()
        else:
            return HttpResponse(None, status=204)
    else:
        return HttpResponseForbidden()
