"""
Copied+modified from rest_framework.permissions, which is licensed under the BSD license:
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

Provides a set of pluggable permission policies.
"""
from __future__ import unicode_literals

import hashlib
from datetime import datetime
from random import random
from logging import getLogger

from gui.models.permission import (
    NetworkAdminPermission,
    ImageAdminPermission,
    ImageImportAdminPermission,
    TemplateAdminPermission,
    IsoAdminPermission,
    DnsAdminPermission,
    UserAdminPermission,
    MonitoringAdminPermission,
)

__all__ = (
    'AllowAny',
    'IsAuthenticated',
    'IsAuthenticatedOrReadOnly',
    'HasAPIAccessPermission',

    'IsSuperAdmin',
    'IsAdmin',
    'IsSuperAdminOrReadOnly',
    'IsAdminOrReadOnly',

    'IsImageAdmin',
    'IsMonitoringAdmin',

    'IsAnyDcImageAdmin',
    'IsAnyDcImageImportAdmin',
    'IsAnyDcNetworkAdmin',
    'IsAnyDcTemplateAdmin',
    'IsAnyDcIsoAdmin',
    'IsAnyDcDnsAdmin',
    'IsAnyDcUserAdmin',

    'IsProfileOwner',
    'IsAnyDcUserAdminOrProfileOwner',
)

logger = getLogger(__name__)

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


####
# Helper functions that are used for checking permissions in API.
########

def generate_security_hash(random_token, private_key):
    """
    Method for security_hash generation
    """
    mh = hashlib.md5()
    mh.update(random_token)
    mh.update(private_key)

    return mh.hexdigest()


def generate_random_security_hash():
    return generate_security_hash(str(random()), str(datetime.now()))


def get_security_data_from_request(request):
    """
    Handle request data from both GET and POST and return data for validation
    """
    security_data = request.POST.get('security_data', '')
    security_hash = request.POST.get('security_hash', '')

    logger.debug('security_data: %s', security_data)
    logger.debug('security_hash: %s', security_hash)

    return security_data, security_hash


def check_security_data(request, private_key):
    """
    Method that verifies the security hash, according to a private_key. Passed in security_hash in a request
    has to be the same as security_data and private_key MD5 hash.
    """
    security_data, security_hash = get_security_data_from_request(request)

    if generate_security_hash(security_data, private_key) == security_hash:
        logger.debug('Security token verified')
        return True

    logger.error('Security token verification failed.')
    logger.debug('Our verification security_hash: %s', generate_security_hash(security_data, private_key))

    return False


####
# Classic Django Rest Framework permissions used by @permission_classes().
########

class BasePermission(object):
    """
    A base class from which all permission classes should inherit.
    """
    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return True

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return True


class AllowAny(BasePermission):
    """
    Allow any access.
    This isn't strictly required, since you could use an empty
    permission_classes list, but it's useful because it makes the intention
    more explicit.
    """
    def has_permission(self, request, view):
        return True


class IsAuthenticated(BasePermission):
    """
    Allows access only to authenticated users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated()


class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class IsAuthenticatedOrReadOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.user and request.user.is_authenticated()


class HasAPIAccessPermission(BasePermission):
    """
    Check if user is permitted to use the API when requesting /api/.. via HTTP.
    This permission should be always the last one in permission_classes list.
    """
    def has_permission(self, request, view):
        if request.path.startswith('/api/'):
            if request.user and request.user.api_access:
                return True
            else:
                return False

        return True


####
# Custom permissions used by @request_data()
########

class DcBasePermission(object):
    """
    This is our own implementation of a BasePermission.
    It validates when initialized and has a the has_permission() has a slightly different signature.
    It is used and checked in api.decorators._request_data.
    """
    _allowed_ = False

    def __init__(self, *args, **kwargs):
        self._allowed_ = self.has_permission(*args, **kwargs)

    def __bool__(self):
        return self._allowed_
    __nonzero__ = __bool__

    # noinspection PyMethodMayBeStatic
    def has_permission(self, request, view, args, kwargs):
        # You will probably want to do this: "my_permission" in request.dc_user_permissions
        return True


class IsSuperAdminOrReadOnly(DcBasePermission):
    """
    Allows access only to admin users or regular users to read-only stuff if the request method is GET.
    """
    def has_permission(self, request, view, args, kwargs):
        return request.user.is_staff or request.method in SAFE_METHODS


class IsSuperAdmin(DcBasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view, args, kwargs):
        return request.user.is_staff


class IsAdminOrReadOnly(DcBasePermission):
    """
    Allows access only to admin users or regular users to read-only stuff if the request method is GET.
    """
    def has_permission(self, request, view, args, kwargs):
        return request.method in SAFE_METHODS or request.user.is_admin(request)


class IsAdmin(DcBasePermission):
    """
    Allows access only to admin users or datacenter admins.
    """
    def has_permission(self, request, view, args, kwargs):
        return request.user.is_admin(request)


class DcPermission(DcBasePermission):
    """
    Boiler plate for DC-related permissions.
    """
    admin_required = False
    permission = None

    def has_permission(self, request, view, args, kwargs):
        if request.user.is_staff or self.permission.name in request.dc_user_permissions:
            if self.admin_required and not request.user.is_admin(request):
                return False

            request.dcs = [request.dc]
            return True

        return False


class AnyDcPermission(DcBasePermission):
    """
    Boiler plate for DC-related permissions with request.dcs parameter.
    """
    admin_required = False
    permission = None

    def has_permission(self, request, view, args, kwargs):
        request.dcs = request.user.get_permission_dcs(self.permission.name, admin_required=self.admin_required)

        if request.user.is_staff:
            return True

        return bool(request.dcs)


class IsMonitoringAdmin(DcPermission):
    """
    Allows access only to SuperAdmins or users with monitoring_admin permission in a specific DC.
    """
    admin_required = True
    permission = MonitoringAdminPermission


class IsImageAdmin(DcPermission):
    """
    Allows access only to SuperAdmins or users with image_admin permission.
    """
    admin_required = True
    permission = ImageAdminPermission


class IsAnyDcImageAdmin(AnyDcPermission):
    """
    Allows access only to SuperAdmins or users with image_admin permission in any DC.
    """
    admin_required = True
    permission = ImageAdminPermission


class IsAnyDcImageImportAdmin(AnyDcPermission):
    """
    Allows access only to SuperAdmins or users with image_import_admin permission in any DC.
    """
    admin_required = True
    permission = ImageImportAdminPermission


class IsAnyDcNetworkAdmin(AnyDcPermission):
    """
    Allows access only to SuperAdmins or users with network_admin permission in any DC.
    """
    admin_required = True
    permission = NetworkAdminPermission


class IsAnyDcTemplateAdmin(AnyDcPermission):
    """
    Allows access only to SuperAdmins or users with template_admin permission in any DC.
    """
    admin_required = True
    permission = TemplateAdminPermission


class IsAnyDcIsoAdmin(AnyDcPermission):
    """
    Allows access only to SuperAdmins or users with iso_admin permission in any DC.
    """
    admin_required = True
    permission = IsoAdminPermission


class IsAnyDcDnsAdmin(AnyDcPermission):
    """
    Allows access only to SuperAdmins or users with dns_admin permission in any DC.
    """
    admin_required = True
    permission = DnsAdminPermission

    def has_permission(self, *args, **kwargs):
        """Allow access to everyone, because DomainOwners don't have to have DC admin permissions.
        More permission checks are performed inside get_domains() and get_domain()."""
        super(IsAnyDcDnsAdmin, self).has_permission(*args, **kwargs)
        return True


class IsAnyDcUserAdmin(AnyDcPermission):
    """
    Allows access only to SuperAdmins or users with user_admin permission in any DC.
    """
    admin_required = True
    permission = UserAdminPermission


class IsProfileOwner(DcBasePermission):
    """
    Allows access only to SuperAdmin users or regular user if he is the profile owner.
    """
    @staticmethod
    def get_username(args, kwargs):
        # WARNING: This check can be easily bypassed so don't forget to perform a double check inside your view!
        try:
            username = args[0]
        except IndexError:
            username = kwargs['username']
        except KeyError:
            username = None

        return username

    @classmethod
    def check(cls, request, args, kwargs):
        username = cls.get_username(args, kwargs)

        if username and request.user.username == username:
            request.is_profile_owner = True
            return True
        else:
            return False

    def has_permission(self, request, view, args, kwargs):
        if request.user.is_staff:
            return True
        else:
            return self.check(request, args, kwargs)


class IsAnyDcUserAdminOrProfileOwner(AnyDcPermission):
    """
    Allows access only to SuperAdmin, UserAdmin users or regular user if he is the profile owner.
    """
    admin_required = True
    permission = UserAdminPermission

    def has_permission(self, request, view, args, kwargs):
        if IsProfileOwner.check(request, args, kwargs):
            return True
        else:
            return super(IsAnyDcUserAdminOrProfileOwner, self).has_permission(request, view, args, kwargs)
