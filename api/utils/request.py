from copy import copy

from django.http.request import HttpRequest

from api.request import Request


REQUEST_CLASSES = (HttpRequest, Request)


def is_request(obj):
    """
    Return true if obj is a request object.
    """
    return isinstance(obj, REQUEST_CLASSES) and hasattr(obj, 'dc')


def set_request_method(request, method, copy_request=True):
    """
    This helper function changes the request.method attribute. By default, it creates a copy of the request object
    and the caller should use the new copy. Callers who already have a copy of the request object will use the
    copy_request=False parameter (call_api_view() and get_dummy_request()).
    """
    if copy_request:
        request = copy(request)

    if isinstance(request, Request):
        # RestFramework's request.method is an wrapper for accessing the original request.method.
        # noinspection PyProtectedMember
        request._request.method = method
    else:
        request.method = method

    return request


def get_dummy_request(dc, method=None, user=None, system_user=False):
    """
    Return dummy request object.
    """
    request = HttpRequest()
    request.csrf_processing_done = True
    request.dc = dc

    if method:
        request = set_request_method(request, method, copy_request=False)

    if system_user:
        from api.task.utils import get_system_task_user
        request.user = get_system_task_user()
    elif user:
        request.user = user

    return request
