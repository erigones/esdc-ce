from logging import getLogger
from hashlib import md5
from datetime import datetime, timedelta

from django.http import HttpResponse
import requests

from api.decorators import api_view, permission_classes
from api.email import sendmail
from vms.models import DefaultDc

__all__ = ('sms_send',)

logger = getLogger(__name__)

PROVIDER_NAME = 'SMSAPI (former HQSMS)'

CALLBACK_STATUS_CODES = {
    '401': 'NOT_FOUND (Wrong ID or report has expired)',
    '402': 'EXPIRED (Messages expired)',
    '403': 'SENT (Message is sent)',
    '404': 'DELIVERED (Message is delivered to recipient)',
    '405': 'UNDELIVERED (Message is undelivered, invalid number, roaming error etc)',
    '406': 'FAILED (Sending message failed - please report it to SMSAPI)',
    '407': 'REJECTED (Message is undelivered invalid number, roaming error etc)',
    '408': 'UNKNOWN (No report, message may be either delivered or not)',
    '409': 'QUEUED (Message is waiting to be sent)',
    '410': 'ACCEPTED (Message is delivered to operator)',
}
CALLBACK_STATUS_CODES_OK = frozenset(['403', '404', '409', '410'])


def login_data():
    """
    Login credentials in SMSAPI (former HQSMS) service
    """
    dc1_settings = DefaultDc().settings
    mh = md5()
    mh.update(dc1_settings.SMS_SMSAPI_PASSWORD)
    expire = datetime.now() + timedelta(hours=dc1_settings.SMS_EXPIRATION_HOURS)

    return {
        'username': dc1_settings.SMS_SMSAPI_USERNAME,
        'password': mh.hexdigest(),
        'from': dc1_settings.SMS_SMSAPI_FROM,
        'expiration_date': expire.strftime('%s'),
    }


def _smsapi_response_adapter(response):
    """
    Adapter to correct response code if there is error with the SMS.
    SMSAPI return response status code 200 but text of the response is ERROR #230
    """
    if response.status_code == requests.codes.ok and response.text.startswith('ERROR'):
        logger.warning('Response got status code %s and contain "%s". Updating status code to %s!',
                       response.status_code, response.text, 406)
        response.status_code = 406

    return response


def sms_send(phone, message):
    """
    Send text message.
    Function shall not be called directly as validation happens in view above.
    """
    data = login_data()
    data['to'] = phone.replace('+', '')
    data['message'] = message

    return _smsapi_response_adapter(requests.post('https://api.smsapi.com/sms.do', data))


def _get_callback_param(data, attr, index):
    value = data.get(attr, None)

    if value:
        try:
            return value.split(',')[index]
        except IndexError:
            return value

    return None


@api_view(('GET',))
@permission_classes(())
def callback(request):
    """
    Function that will be called by SMSAPI (former HQSMS) after sms has been send out.

    SMSAPI: After updating message status in SMSAPI system the update will be sent to callback script
    (1 to 5 statuses in one request). Parameter will be sent using GET method separated by commas.
    """
    params = request.GET
    msgs = params['MsgId'].split(',')
    logger.info('Received SMSAPI (former HQSMS) callback for %d message(s): %s', len(msgs), msgs)
    log_msg = 'SMSAPI (former HQSMS) callback: SMS to %(to)s has status %(status)s at %(donedate)s UTC ' \
              'sent from account: %(username)s with SMSAPI ID %(MsgId)s.'

    for i, msgid in enumerate(msgs):
        context = {
            'MsgId': msgid,
            'to': _get_callback_param(params, 'to', i),  # WARNING: this parameter is not officially documented
            'username': _get_callback_param(params, 'username', i),
        }

        status = _get_callback_param(params, 'status', i)
        status_is_ok = status in CALLBACK_STATUS_CODES_OK
        context['status'] = CALLBACK_STATUS_CODES.get(status)

        try:
            donedate = float(_get_callback_param(params, 'donedate', i))
        except ValueError:
            donedate = 0
        context['donedate'] = datetime.fromtimestamp(donedate)

        if status_is_ok:
            logger.info(log_msg % context)
        else:
            dc1_settings = DefaultDc().settings
            logger.error(log_msg % context)
            sendmail(
                None,
                'smsapi/callback_sms_failed_subject.txt',
                'smsapi/callback_sms_failed.txt',
                from_email=dc1_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[dc1_settings.SUPPORT_EMAIL],
                fail_silently=True,
                extra_context=context,
            )

    return HttpResponse(content='OK', status=200)
