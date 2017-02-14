"""
Some parts are copied from rest_framework.exceptions, which is licensed under the BSD license:
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

Handled exceptions raised by REST framework.

In addition Django's built in 403 and 404 exceptions are handled.
(`django.http.Http404` and `django.core.exceptions.PermissionDenied`)
"""
from __future__ import unicode_literals

import math

from django.utils.encoding import force_text
from django.utils.translation import ungettext, ugettext_lazy as _
from django.db import (
    DatabaseError,
    OperationalError as DatabaseOperationalError,
    InterfaceError as DatabaseInterfaceError,
)
from redis.exceptions import (
    TimeoutError as RedisTimeoutError,
    ConnectionError as RedisConnectionError,
)
from kombu.exceptions import (
    TimeoutError as RabbitTimeoutError,
    ConnectionError as RabbitConnectionError,
)

from api import status


# List of operational errors that affect the application in a serious manner
# (e.g. callback tasks that fail because of this must be retried)
OPERATIONAL_ERRORS = (
    DatabaseOperationalError,
    DatabaseInterfaceError,
    RabbitConnectionError,
    RabbitTimeoutError,
    RedisTimeoutError,
    RedisConnectionError,
)


class APIException(Exception):
    """
    Base class for REST framework exceptions.
    Subclasses should provide `.status_code` and `.default_detail` properties.
    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('A server error occurred.')

    def __init__(self, detail=None):
        if detail is None:
            self.detail = force_text(self.default_detail)
        else:
            self.detail = force_text(detail)

    def __str__(self):
        return self.detail


class TransactionError(DatabaseError):
    """Use this to break atomic transactions"""
    pass


class ObjectAPIException(APIException):
    """Inject object's name or model's verbose name into detail"""
    default_object_name = _('Object')
    default_model = None

    def __init__(self, detail=None, object_name=None, model=None, task_id=None):
        super(ObjectAPIException, self).__init__(detail=detail)
        self.task_id = task_id

        if not object_name:
            model = model or self.default_model
            if model:
                # noinspection PyProtectedMember
                object_name = model._meta.verbose_name_raw
            else:
                object_name = self.default_object_name
        self.detail = self.detail.format(object=object_name)


class BadRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Bad request')


class ParseError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Malformed request')


class AuthenticationFailed(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Incorrect authentication credentials.')


class NotAuthenticated(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Authentication credentials were not provided.')


class PermissionDenied(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('You do not have permission to perform this action.')


class NotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Not found')


class MethodNotAllowed(APIException):
    status_code = status.HTTP_405_METHOD_NOT_ALLOWED
    default_detail = _('Method "{method}" not allowed.')

    def __init__(self, method, detail=None):
        if detail is None:
            self.detail = force_text(self.default_detail).format(method=method)
        else:
            self.detail = force_text(detail)


class NotAcceptable(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    default_detail = _('Could not satisfy the request Accept header.')

    def __init__(self, detail=None, available_renderers=None):
        if detail is None:
            self.detail = force_text(self.default_detail)
        else:
            self.detail = force_text(detail)
        self.available_renderers = available_renderers


class ObjectNotFound(ObjectAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('{object} not found')


class ObjectAlreadyExists(ObjectAPIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    default_detail = _('{object} already exists')


class ObjectOutOfRange(ObjectAPIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    default_detail = _('{object} out of range')


class ItemNotFound(ObjectNotFound):
    default_object_name = _('Item')


class ItemAlreadyExists(ObjectAlreadyExists):
    default_object_name = _('Item')


class ItemOutOfRange(ObjectOutOfRange):
    default_object_name = _('Item')


class InvalidInput(APIException):
    status_code = status.HTTP_412_PRECONDITION_FAILED
    default_detail = _('Invalid input')


class UnsupportedMediaType(APIException):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = _('Unsupported media type "{media_type}" in request.')

    def __init__(self, media_type, detail=None):
        if detail is None:
            self.detail = force_text(self.default_detail).format(media_type=media_type)
        else:
            self.detail = force_text(detail)


class NodeIsNotOperational(APIException):
    status_code = status.HTTP_423_LOCKED
    default_detail = _('Node is not operational')


class VmIsNotOperational(APIException):
    status_code = status.HTTP_423_LOCKED
    default_detail = _('VM is not operational')


class VmIsLocked(APIException):
    status_code = status.HTTP_423_LOCKED
    default_detail = _('VM is locked or has slave VMs')


class TaskIsAlreadyRunning(APIException):
    status_code = status.HTTP_423_LOCKED
    default_detail = _('Task is already running')


class NodeHasPendingTasks(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('Node has pending tasks')


class VmHasPendingTasks(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('VM has pending tasks')


class ExpectationFailed(APIException):
    status_code = status.HTTP_417_EXPECTATION_FAILED
    default_detail = _('Expectation Failed')


class PreconditionRequired(APIException):
    status_code = status.HTTP_428_PRECONDITION_REQUIRED
    default_detail = _('Precondition Required')


class FailedDependency(APIException):
    status_code = status.HTTP_424_FAILED_DEPENDENCY
    default_detail = _('Failed Dependency')


class Throttled(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _('Request was throttled.')
    extra_detail_singular = 'Expected available in {wait} second.'
    extra_detail_plural = 'Expected available in {wait} seconds.'

    def __init__(self, wait=None, detail=None):
        if detail is None:
            self.detail = force_text(self.default_detail)
        else:
            self.detail = force_text(detail)

        if wait is None:
            self.wait = None
        else:
            self.wait = math.ceil(wait)
            self.detail += ' ' + force_text(ungettext(
                self.extra_detail_singular.format(wait=self.wait),
                self.extra_detail_plural.format(wait=self.wait),
                self.wait
            ))


class APIError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('Internal Server Error')


class OperationNotSupported(APIException):
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    default_detail = _('Operation not supported')


class GatewayTimeout(APIException):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    default_detail = _('Gateway Timeout')
