from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect
from django.core.urlresolvers import reverse


def staff_required(fun):
    """
    Decorator for checking staff users. Return 403 if user is not staff member.
    """
    def wrap(request, *args, **kwargs):
        if request.user.is_staff:
            return fun(request, *args, **kwargs)
        return HttpResponseForbidden()
    return wrap


def admin_required(fun):
    """
    Decorator for checking staff users or DC owners.
    """
    def wrap(request, *args, **kwargs):
        if request.user.is_admin(request):
            return fun(request, *args, **kwargs)
        return HttpResponseForbidden()
    return wrap


def logout_required(fun):
    """
    Not-logged-in decorator.
    Use for pages that do not require login. If a user is logged in and accessing such a page, he should be redirected
    to some meaningful page.
    """
    def wrap(request, *args, **kwargs):
        if request.user and request.user.is_authenticated():
            return redirect(settings.LOGIN_REDIRECT_URL)
        return fun(request, *args, **kwargs)
    return wrap


def profile_required(fun):
    """
    Profile decorator.
    Use everywhere where you have to be sure, that user has all required profile items filled in and all items are
    verified. Redirect user to profile page if some information in user profile are missing or are not verified.
    """
    def wrap(request, *args, **kwargs):
        dc_settings = request.dc.settings
        if dc_settings.REGISTRATION_ENABLED and request.user and request.user.userprofile and not request.user.is_staff:
            if not request.user.userprofile.is_ok():
                return redirect(reverse('profile') + '?profile_required=true')
        return fun(request, *args, **kwargs)
    return wrap


def ajax_required(fun):
    """
    AJAX request required decorator
    use it in your views:

    @ajax_required
    def my_view(request):
        ....
    http://djangosnippets.org/snippets/771/
    """
    def wrap(request, *args, **kwargs):
        if request.is_ajax():
            return fun(request, *args, **kwargs)
        return HttpResponseBadRequest()
    return wrap


def permission_required(permission):
    """
    GUI decorator for checking if user has permission.name in current DC.
    """
    def permission_required_decorator(fun):
        def wrap(request, *args, **kwargs):
            if request.user.is_staff or permission.name in request.dc_user_permissions:
                return fun(request, *args, **kwargs)
            return HttpResponseForbidden()
        return wrap
    return permission_required_decorator
