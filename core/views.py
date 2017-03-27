from django.views import defaults
from django.http import HttpResponseNotFound, HttpResponseServerError, HttpResponseForbidden


def forbidden(request):
    """
    Custom 403 handler.
    """
    if request.path.startswith('/api/'):
        return HttpResponseForbidden('You do not have permission to access this resource',
                                     content_type='application/json')
    return defaults.permission_denied(request)


def page_not_found(request):
    """
    Custom 404 handler.
    """
    if request.path.startswith('/api/'):
        return HttpResponseNotFound('Resource not found', content_type='application/json')
    return defaults.page_not_found(request)


def server_error(request):
    """
    Custom 500 error handler.
    """
    if request.path.startswith('/api/'):
        return HttpResponseServerError('Server Error', content_type='application/json')
    return defaults.server_error(request)
