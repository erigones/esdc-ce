from logging import getLogger

from gui.middleware import MiddlewareMixin
from vms.models import Dc, DummyDc

logger = getLogger(__name__)


class DcMiddleware(MiddlewareMixin):
    """
    Attach dc attribute to each request.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    # noinspection PyMethodMayBeStatic
    def process_request(self, request):
        dc = getattr(request, 'dc', None)

        if not dc or dc.is_dummy:
            if request.path.startswith('/api/'):
                return  # Managed by ExpireTokenAuthentication and request_data decorator

            if request.user.is_authenticated:
                # Set request.dc for logged in user
                request.dc = Dc.objects.get_by_id(request.user.current_dc_id)
                # Whenever we set a DC we have to set request.dc_user_permissions right after request.dc is available
                request.dc_user_permissions = request.dc.get_user_permissions(request.user)
                # Log this request only for authenticated users
                logger.debug('"%s %s" user="%s" dc="%s" permissions=%s', request.method, request.path,
                             request.user.username, request.dc.name, request.dc_user_permissions)
            else:
                try:
                    # This will get DC also for external views to login and registration pages according to URL
                    request.dc = Dc.objects.get_by_site(request.META['HTTP_HOST'])
                except (KeyError, Dc.DoesNotExist):
                    request.dc = DummyDc()

                # Whenever we set a DC we have to set request.dc_user_permissions right after request.dc is available
                request.dc_user_permissions = frozenset()  # External users have no permissions
