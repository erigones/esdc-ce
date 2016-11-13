from datetime import timedelta
from logging import getLogger

from django.conf import settings

from api import status as scode
from api.authtoken.models import Token
from api.accounts.base.serializers import APIAuthTokenSerializer
from api.decorators import api_view, permission_classes, setting_required
from api.response import Response
from gui.accounts.utils import get_client_ip
from vms.models import Dc

auth_logger = getLogger('api.auth')

__all__ = ('api_login', 'api_logout')

AUTHTOKEN_TIMEDELTA = timedelta(seconds=settings.AUTHTOKEN_DURATION)


@api_view(('POST',))
@permission_classes(())
@setting_required('API_ENABLED', default_dc=True)
def api_login(request):
    """
    Function used for API login validation and authentication
    (:http:post:`POST </accounts/login>`). There are two required parameters.

    .. http:post:: /accounts/login

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |APIAccess|
        :Asynchronous?:
            * |async-no|
        :arg string data.username: **required** - Username used for authentication
        :arg string data.password: **required** - Password used for authentication
        :status 200: Login successful
        :status 400: Bad request
    """
    serializer = APIAuthTokenSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.object['user']
        token, created = Token.objects.get_or_create(user=user)

        if not created:  # Old Token - regenerate token and datetime
            # TODO: We do this by deleting the old token (could be done better)
            token.delete()
            token = Token.objects.create(user=user)

        auth_logger.info('User %s successfully logged in from %s (%s)',
                         user, get_client_ip(request), request.META.get('HTTP_USER_AGENT', ''))

        request.user = user
        request.dc = Dc.objects.get_by_id(user.current_dc_id)

        return Response({
            'token': token.key,
            'expires': (token.created + AUTHTOKEN_TIMEDELTA).isoformat(),
            'detail': 'Welcome to Danube Cloud API.'
        }, status=scode.HTTP_200_OK, request=request)

    auth_logger.warning('User %s login failed from %s (%s)',
                        request.data.get('username', None), get_client_ip(request),
                        request.META.get('HTTP_USER_AGENT', ''))

    try:
        error_message = serializer.errors['non_field_errors'][0]
    except (KeyError, IndexError):
        error_message = serializer.errors

    return Response({'detail': error_message}, status=scode.HTTP_400_BAD_REQUEST)


@api_view(('GET',))
def api_logout(request):
    """
    Function used for API logout (:http:get:`GET </accounts/logout>`).

    .. http:get:: /accounts/logout

        :DC-bound?:
            * |dc-no|
        :Permissions:
        :Asynchronous?:
            * |async-no|
        :status 200: Logout successful
        :status 403: Forbidden
    """
    response = Response({'detail': 'Bye.'}, status=scode.HTTP_200_OK, request=request)
    user = None

    # noinspection PyBroadException
    try:
        user = request.user
        request.user = None
        request.auth.delete()
    except:
        pass

    auth_logger.info('User %s successfully logged out from %s (%s)',
                     user, get_client_ip(request), request.META.get('HTTP_USER_AGENT', ''))

    return response
