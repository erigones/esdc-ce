from logging import getLogger

from requests import codes

from api.decorators import api_view, setting_required, request_data_defaultdc
from api.response import BadRequestResponse, OKRequestResponse
from api.sms.permissions import SmsSendPermission
from api.sms.utils import get_current_service

__all__ = ('internal_send', 'send')

logger = getLogger(__name__)


def internal_send(phone, message):
    """
    Function for actual sending message via preferred service.
    """
    use_service = get_current_service()
    logger.debug('Using SMS service %s imported from %s', use_service.PROVIDER_NAME, use_service.__name__)

    # TODO: Proper phone number validation
    if not phone:
        logger.error('Phone number for SMS was not filled in.')
        return False

    # TODO: Proper message validation (size, valid characters, ...)
    if not message:
        logger.error('Message body for SMS was not filled in.')
        return False

    try:
        r = use_service.sms_send(phone, message)
    except Exception as e:
        logger.critical('SMS sending to %s failed!', phone)
        logger.exception(e)
        return False

    if r.status_code == codes.ok:
        logger.info('SMS has been sent to %s, status_code=%s, response="%s"', phone, r.status_code, r.text)
        return True
    else:
        logger.error('SMS to %s was not sent, status_code=%s, response="%s"', phone, r.status_code, r.text)
        logger.debug(r.text)
        return False


@api_view(('POST',))
@request_data_defaultdc(permissions=(SmsSendPermission,))
@setting_required('SMS_ENABLED')  # default_dc=True is implicated by request_data_defaultdc
def send(request, data=None):
    """
    Send (:http:post:`POST </sms/send`) a short text message via preferred SMS provider.

    .. http:post:: /sms/send

        :DC-bound?:
            * |dc-no|
        :Permissions:
        :Asynchronous?:
            * |async-no|
        :arg data.phone: Phone number
        :type data.phone: string
        :arg data.message: Message content
        :type data.message: string
        :status 200: SMS was sent
        :status 400: SMS was not sent
        :status 403: Forbidden

    """
    phone = data.get('phone', '')
    message = data.get('message', '')

    if internal_send(phone, message):
        return OKRequestResponse(request, detail='SMS was sent')
    else:
        return BadRequestResponse(request, detail='SMS was not sent')
