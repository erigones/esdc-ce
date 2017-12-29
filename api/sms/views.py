from logging import getLogger

from api.sms.utils import get_current_service
from api.sms.exceptions import InvalidSMSInput, SMSSendFailed
from vms.models import DefaultDc

__all__ = ('internal_send',)

logger = getLogger(__name__)


def internal_send(phone, message):
    """
    Function for actual sending message via preferred service.
    """
    dc1_settings = DefaultDc().settings

    if not dc1_settings.SMS_ENABLED:
        logger.warning('SMS module is disabled -> ignoring SMS send request to %s!', phone)
        return None

    sms_service = get_current_service(settings=dc1_settings)
    logger.debug('Using SMS service %s imported from %s', sms_service.PROVIDER_NAME, sms_service.__name__)

    # TODO: Proper phone number validation
    if not phone:
        logger.error('Phone number for SMS was not filled in.')
        raise InvalidSMSInput('Missing phone number')

    # TODO: Proper message validation (size, valid characters, ...)
    if not message:
        logger.error('Message body for SMS was not filled in.')
        raise InvalidSMSInput('Missing SMS body')

    try:
        error = sms_service.sms_send(phone, message,
                                     username=dc1_settings.SMS_SERVICE_USERNAME,
                                     password=dc1_settings.SMS_SERVICE_PASSWORD,
                                     from_=dc1_settings.SMS_FROM_NUMBER,
                                     expire_hours=dc1_settings.SMS_EXPIRATION_HOURS)
    except Exception as e:
        logger.critical('SMS sending to %s failed!', phone)
        logger.exception(e)
        raise SMSSendFailed('SMS provider error: %s' % e)

    if error:
        logger.error('SMS to %s was not sent', phone)
        raise SMSSendFailed('SMS send failed: %s' % error)

    logger.info('SMS has been sent to %s', phone)
    return None
