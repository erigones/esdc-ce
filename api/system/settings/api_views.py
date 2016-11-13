import os
from logging import getLogger
from tempfile import NamedTemporaryFile
from subprocess import Popen, PIPE, STDOUT
from django.conf import settings

from api.api_views import APIView
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.system.messages import LOG_SYSTEM_SETTINGS_UPDATE
from api.system.settings.serializers import SSLCertificateSerializer

from vms.models import DefaultDc

logger = getLogger(__name__)


class SystemSettingsView(APIView):
    """
    Update Danube Cloud application.
    """
    SSL_CERTIFICATE_UPDATE_CMD = 'bin/esdc-sslcert-update'
    dc_bound = False

    def __init__(self, request, data):
        super(SystemSettingsView, self).__init__(request)
        self.data = data

    def ssl_certificate(self):
        """PUT /system/settings/ssl-certificate - runs a script, which checks the certificate by running openssl,
        replaces the PEM file and reloads haproxy"""
        assert self.request.dc.id == DefaultDc().id

        ser = SSLCertificateSerializer(self.request, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, dc_bound=False)

        cert = ser.object['cert']
        update_script = os.path.join(settings.PROJECT_DIR, self.SSL_CERTIFICATE_UPDATE_CMD)
        res = {
            'action': 'SSL Certificate Update',
            'returncode': '???',
            'message': ''
        }

        cert_file = NamedTemporaryFile(dir=settings.TMPDIR, mode='w', delete=False)
        cert_file.write(cert)
        cert_file.close()

        try:
            proc = Popen(['sudo', update_script, cert_file.name], bufsize=0, close_fds=True, stdout=PIPE, stderr=STDOUT)
            res['message'], _ = proc.communicate()
            res['returncode'] = proc.returncode
        finally:
            os.remove(cert_file.name)

        if proc.returncode == 0:
            response_class = SuccessTaskResponse
        else:
            response_class = FailureTaskResponse

        return response_class(self.request, res, msg=LOG_SYSTEM_SETTINGS_UPDATE, detail_dict=res, dc_bound=False)
