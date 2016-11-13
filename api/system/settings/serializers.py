from api import serializers as s
from api.validators import validate_pem_cert, validate_pem_key


class SSLCertificateSerializer(s.Serializer):
    """
    Validate update urls and login credentials.
    """
    cert = s.CharField(max_length=2097152, validators=(validate_pem_cert, validate_pem_key))

    def __init__(self, request, *args, **kwargs):
        self.request = request
        super(SSLCertificateSerializer, self).__init__(*args, **kwargs)
