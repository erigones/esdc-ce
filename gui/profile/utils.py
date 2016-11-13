from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.conf import settings

from api.accounts.user.base.serializers import UserSerializer
from api.accounts.user.profile.serializers import UserProfileSerializer


def get_user_serializer(request, user):
    """
    Like GET
    """
    if user is not None:
        return UserSerializer(request, user).data

    return UserSerializer(request, None, many=True).data


def get_userprofile_serializer(request, user):
    """
    Like GET
    """
    if user is not None:
        return UserProfileSerializer(request, user).data

    return UserProfileSerializer(request, None, many=True).data


def impersonate_user(request, user_id):
    if not request.user.is_staff:
        raise PermissionDenied

    request.session['impersonate_id'] = user_id

    return redirect(settings.LOGIN_REDIRECT_URL)


def impersonate_cancel(request):
    # Since this function is only called by views for logged-in users who see the "Cancel impersonation" button
    # the real_user attribute should exist. However, one can also call the view directly (e.g. via the "next="
    # querystring attribute after successful login).
    if not getattr(request, 'real_user', request.user).is_staff:
        raise PermissionDenied

    try:
        del request.session['impersonate_id']
    except KeyError:
        pass

    return redirect('dc_user_list')
