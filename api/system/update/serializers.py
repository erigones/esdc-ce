from api import serializers as s
from api.validators import validate_pem_cert, validate_pem_key


class UpdateSerializer(s.Serializer):
    """
    Validate update urls and login credentials.
    """
    version = s.SafeCharField(required=True, max_length=1024, min_length=2)
    force = s.BooleanField(default=False)
    key = s.CharField(required=False, max_length=102400, validators=(validate_pem_key,))
    cert = s.CharField(required=False, max_length=102400, validators=(validate_pem_cert,))

    def __init__(self, request, *args, **kwargs):
        self.request = request
        super(UpdateSerializer, self).__init__(*args, **kwargs)
