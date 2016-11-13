from api import status
from api.response import Response
from api.decorators import api_view, permission_classes


# noinspection PyUnusedLocal
@api_view(('GET',))
@permission_classes(())
def api_ping(request):
    """
    Function used for API monitoring.

    Accepts :http:method:`get` only.

    .. http:get:: /ping

        :status 200: SUCCESS
    """
    return Response('pong', status=status.HTTP_200_OK)
