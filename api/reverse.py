"""
Copied+modified from rest_framework.reverse, which is licensed under the BSD license:
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

Provide urlresolver functions that return fully qualified URLs or view names
"""
from __future__ import unicode_literals

from django.urls import NoReverseMatch, reverse as django_reverse
from django.utils import six
from django.utils.functional import lazy


# noinspection PyShadowingBuiltins
def _reverse(viewname, args=None, kwargs=None, request=None, format=None, **extra):
    """
    Same as `django.core.urlresolvers.reverse`, but optionally takes a request
    and returns a fully qualified URL, using the request to get the base URL.
    """
    if format is not None:
        kwargs = kwargs or {}
        kwargs['format'] = format

    url = django_reverse(viewname, args=args, kwargs=kwargs, **extra)

    if request:
        return request.build_absolute_uri(url)

    return url


# noinspection PyShadowingBuiltins
def reverse(viewname, args=None, kwargs=None, request=None, format=None, **extra):
    """
    If versioning is being used then we pass any `reverse` calls through
    to the versioning scheme instance, so that the resulting URL
    can be modified if needed.
    """
    scheme = getattr(request, 'versioning_scheme', None)

    if scheme is not None:
        try:
            return scheme.reverse(viewname, args, kwargs, request, format, **extra)
        except NoReverseMatch:
            # In case the versioning scheme reversal fails, fallback to the default implementation
            pass

    return _reverse(viewname, args, kwargs, request, format, **extra)


reverse_lazy = lazy(reverse, six.text_type)
