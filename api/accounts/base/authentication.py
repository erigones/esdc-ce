from django.utils import timezone
from django.conf import settings

from api.exceptions import AuthenticationFailed, PermissionDenied
from api.authentication import BaseAuthentication, TokenAuthentication, SessionAuthentication as _SessionAuthentication
from gui.models import User
from vms.models import Dc


def _set_request_dc(request, user):
    if not user.api_access:
        raise PermissionDenied('User account is not allowed to access API')

    # Set datacenter (the vms.middleware.DcMiddleware doesn't work with DRF)
    dc = getattr(request, 'dc', None)

    if not dc or dc.is_dummy:
        request.dc = Dc.objects.get_by_id(user.current_dc_id)  # Can be overridden in request_data decorator
        request.dcs = Dc.objects.none()  # Can be overridden by DcPermission
        request.dc_user_permissions = frozenset()  # Will be overridden in request_data decorator

    return request


class SessionAuthentication(_SessionAuthentication):
    """
    This authentication mechanism is used whenever we call some API function from the web browser (/socket.io).
    """
    def authenticate(self, request):
        auth = super(SessionAuthentication, self).authenticate(request)

        if auth and request.path.startswith('/api/'):  # Someone is most probably calling /api/ from the web browser
            return None

        return auth


class ApiKeyAuthentication(BaseAuthentication):
    """
    Authenticate against api_key header.
    """
    def authenticate(self, request):
        api_key = request.META.get('HTTP_ES_API_KEY', None)

        if not api_key:
            return None

        try:
            user = User.objects.get(api_key=api_key)
        except User.DoesNotExist:
            raise AuthenticationFailed('Invalid API key')
        else:
            # Set datacenter (the vms.middleware.DcMiddleware doesn't work with DRF)
            _set_request_dc(request, user)

        return user, 'api_key'

    def authenticate_header(self, request):
        return 'api_key'


class ExpireTokenAuthentication(TokenAuthentication):
    """
    Add expiration functionality into TokenAuthentication.
    """
    def authenticate(self, request):
        auth = super(ExpireTokenAuthentication, self).authenticate(request)

        if not auth:
            return None

        delta = timezone.now() - auth[1].created

        if delta.total_seconds() > settings.AUTHTOKEN_DURATION:
            return None

        # Set datacenter (the vms.middleware.DcMiddleware doesn't work with DRF)
        _set_request_dc(request, auth[0])

        return auth
