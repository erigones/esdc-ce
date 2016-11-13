from django.views import defaults
from django.http import HttpResponseNotFound, HttpResponseServerError


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
