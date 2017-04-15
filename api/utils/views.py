from logging import getLogger
from copy import copy

from api.views import exception_handler
from api.utils.request import set_request_method

logger = getLogger(__name__)


def call_api_view(request, method, fun, *args, **kwargs):
    """
    A handy wrapper for calling api view functions or classes.
    """
    # We need a shallow copy of the request object because the original request object is still used by our caller
    request = copy(request)

    if method:
        request = set_request_method(request, method, copy_request=False)

    request.disable_throttling = kwargs.pop('disable_throttling', True)
    log_response = kwargs.pop('log_response', False)
    api_class = kwargs.pop('api_class', False)

    try:
        res = fun(request, *args, **kwargs)

        if api_class:
            res = res.response()
    except Exception as ex:
        res = exception_handler(ex, request)
        if res is None:
            raise
        res.exception = True
    finally:
        request.disable_throttling = False

    if log_response:
        logger.info('Called API view %s %s(%s, %s) by user %s in DC %s \n\twith response (%s): %s',
                    method, fun.__name__, args, kwargs, request.user, request.dc, res.status_code, res.data)

    return res
