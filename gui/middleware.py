from django.conf import settings
from django.utils import timezone
from django.http import HttpResponseRedirect

from gui.models import User
from gui.context_processors import print_sql_debug
from gui.exceptions import HttpRedirectException


class MiddlewareMixin(object):
    def __init__(self, get_response=None):
        self.get_response = get_response
        super(MiddlewareMixin, self).__init__()

    def __call__(self, request):
        response = None
        if hasattr(self, 'process_request'):
            response = self.process_request(request)
        if not response:
            response = self.get_response(request)

        if hasattr(self, 'process_response'):
            response = self.process_response(request, response)
        return response


class ExceptionMiddleware(MiddlewareMixin):
    """
    Catch exceptions in this middleware.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def process_exception(self, request, exception):
        if isinstance(exception, HttpRedirectException):
            return HttpResponseRedirect(exception.args[0])


class DebugMiddleware(MiddlewareMixin):
    """
    Print some debugging info to stderr.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def process_response(self, request, response):
        # Print sql debug to stderr if SQL_DEBUG is True
        print_sql_debug()
        return response


class TimezoneMiddleware(MiddlewareMixin):
    """
    This middleware sets the timezone used to display dates in templates to the user's timezone stored in session.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    # noinspection PyMethodMayBeStatic
    def process_request(self, request):
        tz = request.session.get(settings.TIMEZONE_SESSION_KEY)
        if not tz:
            tz = settings.TIME_ZONE
        timezone.activate(tz)


class AjaxMiddleware(MiddlewareMixin):
    """
    Custom middleware for ajax redirects.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    # noinspection PyMethodMayBeStatic
    def process_response(self, request, response):
        if request.is_ajax():
            if isinstance(response, HttpResponseRedirect):
                if request.user.is_authenticated:
                    response.status_code = 278
                else:
                    response.status_code = 279
        return response


class ImpersonateMiddleware(MiddlewareMixin):
    """
    Allow admin user to work in GUI as a regular user of choice.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    # noinspection PyMethodMayBeStatic
    def process_request(self, request):
        request.impersonated = False
        if request.user.is_staff and 'impersonate_id' in request.session:
            user_id = request.session['impersonate_id']
            if user_id:
                try:
                    new_user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    del request.session['impersonate_id']
                else:
                    request.impersonated = True
                    if request.path.startswith('/' + settings.ADMIN_URL):
                        request.new_user = new_user
                    else:
                        request.real_user = request.user
                        request.user = new_user
            else:
                del request.session['impersonate_id']
