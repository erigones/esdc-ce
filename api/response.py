"""
Copied+modified from rest_framework.response, which is licensed under the BSD license:
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

The Response class in REST framework is similar to HTTPResponse, except that
it is initialized with unrendered data, instead of a pre-rendered string.
The appropriate renderer is called during Django's template response rendering.

Simple response classes used mainly by internal api views.

Have a look in to api.task.response for more response classes and wider information about API response convention.
"""
from __future__ import unicode_literals

from django.http import HttpResponse
from django.template.response import SimpleTemplateResponse
from django.utils import six
# noinspection PyUnresolvedReferences
from django.utils.six.moves.http_client import responses

from api import status
from api.renderers import JSONRenderer
from core.version import __version__


class Response(SimpleTemplateResponse):
    """
    An HttpResponse that allows its data to be rendered into arbitrary media types.
    """
    # noinspection PyShadowingNames
    def __init__(self, data=None, status=None, template_name=None, headers=None, exception=False, content_type=None,
                 request=None):
        """
        Alters the init arguments slightly.
        For example, drop 'template_name', and instead use 'data'.
        Setting 'renderer' and 'media_type' will typically be deferred,
        For example being set automatically by the `APIView`.
        """
        super(Response, self).__init__(None, status=status)
        self.data = data
        self.template_name = template_name
        self.exception = exception
        self.content_type = content_type

        if headers:
            for name, value in six.iteritems(headers):
                self[name] = value

        if request:
            self.set_response_headers(request)

    @property
    def rendered_content(self):
        renderer = getattr(self, 'accepted_renderer', None)
        accepted_media_type = getattr(self, 'accepted_media_type', None)
        context = getattr(self, 'renderer_context', None)

        assert renderer, ".accepted_renderer not set on Response"
        assert accepted_media_type, ".accepted_media_type not set on Response"
        assert context, ".renderer_context not set on Response"
        context['response'] = self

        media_type = renderer.media_type
        charset = renderer.charset
        content_type = self.content_type

        if content_type is None and charset is not None:
            content_type = "{0}; charset={1}".format(media_type, charset)
        elif content_type is None:
            content_type = media_type
        self['Content-Type'] = content_type

        ret = renderer.render(self.data, accepted_media_type, context)

        if isinstance(ret, six.text_type):
            assert charset, 'renderer returned unicode, and did not specify a charset value.'
            return bytes(ret.encode(charset))

        if not ret:
            del self['Content-Type']

        return ret

    @property
    def status_text(self):
        """
        Returns reason text corresponding to our HTTP response status code.
        Provided for convenience.
        """
        # TODO: Deprecate and use a template tag instead
        # TODO: Status code text for RFC 6585 status codes
        return responses.get(self.status_code, '')

    def __getstate__(self):
        """
        Remove attributes from the response that shouldn't be cached.
        """
        state = super(Response, self).__getstate__()

        for key in ('accepted_renderer', 'renderer_context', 'resolver_match', 'client', 'request',
                    'json', 'wsgi_request'):
            if key in state:
                del state[key]

        state['_closable_objects'] = []

        return state

    def set_response_headers(self, request, **headers):
        """Set custom Danube Cloud headers."""
        self['es_version'] = __version__

        try:
            self['es_username'] = request.user.username
        except AttributeError:
            pass

        try:
            self['es_dc'] = request.dc.name
        except AttributeError:
            pass

        for key, val in headers.items():
            self[key] = val


class BadRequestResponse(Response):
    """
    Response class for bad requests.
    """
    # noinspection PyUnusedLocal
    def __init__(self, request, detail='Bad request', *args, **kwargs):
        msg = {'detail': detail}
        if 'status' not in kwargs:
            kwargs['status'] = status.HTTP_400_BAD_REQUEST
        super(BadRequestResponse, self).__init__(msg, *args, **kwargs)


class OKRequestResponse(Response):
    """
    Response class for good requests.
    """
    # noinspection PyUnusedLocal
    def __init__(self, request, detail='OK', *args, **kwargs):
        msg = {'detail': detail}
        if 'status' not in kwargs:
            kwargs['status'] = status.HTTP_200_OK
        super(OKRequestResponse, self).__init__(msg, *args, **kwargs)


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders it's content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)
