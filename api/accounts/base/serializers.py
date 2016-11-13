from api import serializers as s
from api.authtoken.serializers import AuthTokenSerializer


class APIAuthTokenSerializer(AuthTokenSerializer):
    """
    Add some more validation into the AuthTokenSerializer.
    """
    def validate(self, attrs):
        attrs = super(APIAuthTokenSerializer, self).validate(attrs)

        if not attrs['user'].api_access:
            raise s.ValidationError('User account is not allowed to access API.')

        return attrs
