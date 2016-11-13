from django.http.request import HttpRequest

from api.request import clone_request, Request


REQUEST_CLASSES = (HttpRequest, Request)


def is_request(obj):
    """
    Return true if obj is a request object.
    """
    return isinstance(obj, REQUEST_CLASSES) and hasattr(obj, 'dc')


def set_request_method(request, method):
    """
    Django HttpRequest.method is mutable, but RestFramework Request.method is not.
    """
    if request.method != method:
        if isinstance(request, Request):
            req = clone_request(request, method)
            if hasattr(request, 'dc'):
                req.dc = request.dc
            return req

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
        request = set_request_method(request, method)

    if system_user:
        from api.task.utils import get_system_task_user
        request.user = get_system_task_user()
    elif user:
        request.user = user

    return request
