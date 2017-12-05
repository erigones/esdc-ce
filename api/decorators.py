"""
Copied+modified from rest_framework.decorators, which is licensed under the BSD license:
*******************************************************************************
Copyright (c) 2011-2016, Tom Christie
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.
Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*******************************************************************************

The most important decorator in this module is `@api_view`, which is used
for writing function-based views with REST framework.

There are also various decorators for setting the API policies on function
based views, as well as the `@detail_route` and `@list_route` decorators, which are
used to annotate methods on viewsets that should be included by routers.
"""
from __future__ import unicode_literals

import types
from logging import getLogger
from functools import wraps, partial

from django.conf import settings
from django.http import Http404
from django.utils import six
from django.utils.decorators import available_attrs
from django.core.exceptions import PermissionDenied

from api.views import View
from api.utils.request import is_request
from api.dc.utils import get_dc
from vms.models import Dc, DefaultDc, DummyDc

logger = getLogger(__name__)


def api_view(http_method_names=None):
    """
    Decorator that converts a function-based view into an APIView subclass.
    Takes a list of allowed methods for the view as an argument.
    """
    http_method_names = ['GET'] if (http_method_names is None) else http_method_names

    def decorator(func):

        # noinspection PyPep8Naming
        WrappedAPIView = type(
            six.PY3 and 'WrappedAPIView' or b'WrappedAPIView',
            (View,),
            {'__doc__': func.__doc__}
        )

        # Note, the above allows us to set the docstring.
        # It is the equivalent of:
        #
        #     class WrappedAPIView(APIView):
        #         pass
        #     WrappedAPIView.__doc__ = func.doc    <--- Not possible to do this

        # api_view applied without (method_names)
        assert not(isinstance(http_method_names, types.FunctionType)), \
            '@api_view missing list of allowed HTTP methods'

        # api_view applied with eg. string instead of list of strings
        assert isinstance(http_method_names, (list, tuple)), \
            '@api_view expected a list of strings, received %s' % type(http_method_names).__name__

        allowed_methods = set(http_method_names) | {'options'}
        WrappedAPIView.http_method_names = [method.lower() for method in allowed_methods]

        # noinspection PyUnusedLocal
        def handler(self, *args, **kwargs):
            return func(*args, **kwargs)

        for method in http_method_names:
            setattr(WrappedAPIView, method.lower(), handler)

        WrappedAPIView.__name__ = func.__name__

        WrappedAPIView.renderer_classes = getattr(func, 'renderer_classes',
                                                  View.renderer_classes)

        WrappedAPIView.parser_classes = getattr(func, 'parser_classes',
                                                View.parser_classes)

        WrappedAPIView.authentication_classes = getattr(func, 'authentication_classes',
                                                        View.authentication_classes)

        WrappedAPIView.throttle_classes = getattr(func, 'throttle_classes',
                                                  View.throttle_classes)

        WrappedAPIView.permission_classes = getattr(func, 'permission_classes',
                                                    View.permission_classes)

        # noinspection PyUnresolvedReferences
        return WrappedAPIView.as_view()
    return decorator


def renderer_classes(_renderer_classes):
    def decorator(func):
        func.renderer_classes = _renderer_classes
        return func
    return decorator


def parser_classes(_parser_classes):
    def decorator(func):
        func.parser_classes = _parser_classes
        return func
    return decorator


def authentication_classes(_authentication_classes):
    def decorator(func):
        func.authentication_classes = _authentication_classes
        return func
    return decorator


def throttle_classes(_throttle_classes):
    def decorator(func):
        func.throttle_classes = _throttle_classes
        return func
    return decorator


def permission_classes(_permission_classes):
    def decorator(func):
        func.permission_classes = _permission_classes
        return func
    return decorator


def request_data(catch_dc=True, force_dc=None, permissions=()):
    def request_data_decorator(fun):
        """
        API view decorator. Updates "data" keyword argument with request.DATA if necessary.
        Also sets the request.dc attribute to current Datacenter if specified.
        And optionally checks additional permissions which cannot be checked via permission_classes,
        because they are related to current datacenter.
        """
        def wrap(request, *args, **kwargs):
            if kwargs.get('data', None) is None:  # data parameter must exist in view function
                if request.method == 'GET':
                    data_key = 'query_params'
                else:
                    data_key = 'data'

                # noinspection PyBroadException
                try:
                    kwargs['data'] = getattr(request, data_key, {})
                except Exception:
                    kwargs['data'] = {}

            dc = getattr(request, 'dc', DummyDc())

            if catch_dc:
                if '/api/dc/' in request.path:
                    try:
                        _dc_name = kwargs.pop('dc')
                    except KeyError:
                        _dc_name = None
                else:
                    _dc_name = None

                dc_name = kwargs['data'].get('dc', _dc_name)

                # Override request.dc set in DcMiddleware
                if dc_name and dc_name != dc.name:
                    request.dc = get_dc(request, dc_name)

            if force_dc and (force_dc != request.dc.id or dc.is_dummy):
                # Override request.dc set in DcMiddleware and by catch_dc
                # WARNING: Make sure that the user has rights to access this DC
                request.dc = Dc.objects.get_by_id(force_dc)

            # Whenever we set a DC we have to set request.dc_user_permissions right after request.dc is available
            request.dc_user_permissions = request.dc.get_user_permissions(request.user)
            # request.dcs is used by some DC-mixed views - can be overridden by DcPermission
            request.dcs = Dc.objects.none()

            logger.debug('"%s %s (%s)" user="%s" dc="%s" permissions=%s', request.method, fun.__name__, request.path,
                         request.user.username, request.dc.name, request.dc_user_permissions)

            # Run permission checks
            for perm in permissions:
                if not perm(request, fun, args, kwargs):
                    logger.error('Request by user "%s" to access API call "%s %s(%s, %s)" was denied by %s permission '
                                 'in DC "%s"!',
                                 request.user, request.method, fun.__name__, args, kwargs, perm.__name__, request.dc)
                    raise PermissionDenied

            return fun(request, *args, **kwargs)

        wrap.__name__ = fun.__name__
        wrap.__doc__ = fun.__doc__

        return wrap
    return request_data_decorator


request_data_nodc = partial(request_data, catch_dc=False)
request_data_defaultdc = partial(request_data, catch_dc=False, force_dc=settings.VMS_DC_DEFAULT)


def setting_required(setting_name, dc_bound=True, default_dc=False, check_settings=True):
    """
    API / GUI decorator for checking DC settings.
    """
    def setting_required_decorator(fun):
        def wrap(request, *args, **kwargs):
            if check_settings:
                opt = getattr(settings, setting_name)
            else:
                opt = True

            if default_dc:
                opt = getattr(DefaultDc().settings, setting_name) and opt
            elif dc_bound:
                try:
                    opt = getattr(request.dc.settings, setting_name) and opt
                except AttributeError:
                    pass

            if opt:
                return fun(request, *args, **kwargs)
            else:
                raise Http404

        wrap.__name__ = fun.__name__
        wrap.__doc__ = fun.__doc__

        return wrap
    return setting_required_decorator


def catch_exception(fun):
    """
    Used as decorator to catch all exceptions and log them without breaking the inner function.
    Can be disabled by using the fail_silently keyword argument, which won't be passed to inner function.
    """
    @wraps(fun, assigned=available_attrs(fun))
    def wrap(*args, **kwargs):
        if kwargs.pop('fail_silently', True):
            try:
                return fun(*args, **kwargs)
            except Exception as e:
                logger.exception(e)
                logger.error('Got exception when running %s(%s, %s): %s.', fun.__name__, args, kwargs, e)
        else:
            return fun(*args, **kwargs)

    return wrap


def catch_api_exception(fun):
    """
    Like catch_exception above, but it logs the exception caught.
    """
    from api.task.utils import task_log_exception  # circular imports

    @wraps(fun, assigned=available_attrs(fun))
    def wrap(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except Exception as e:
            logger.exception(e)
            logger.error('Got exception when running %s(%s, %s): %s.', fun.__name__, args, kwargs, e)

            for arg in args:
                if is_request(arg):
                    try:
                        task_log_exception(arg, e, task_id=getattr(e, 'task_id', None))
                    except Exception as exc:
                        logger.exception(exc)
                    break
            else:
                logger.warning('API exception could not be logged into task log')

    return wrap
