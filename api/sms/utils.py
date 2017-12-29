from vms.models import DefaultDc
# SMS services
# Must be imported this way and the views modules should have a sms_send function and PROVIDER_NAME constant
import api.sms.smsapi.views
from api.sms.exceptions import InvalidSMSService

SMS_SERVICES = (
    ('smsapi', api.sms.smsapi.views),
)


def get_services():
    """
    Returns list of SMS service providers which can be used as choices form field parameter.
    """
    # noinspection PyShadowingBuiltins
    return [(service, module.PROVIDER_NAME) for service, module in SMS_SERVICES]


def get_current_service(settings=None):
    """
    Function that list supported services for sending text messages.
    """
    if not settings:
        settings = DefaultDc().settings  # dc1_settings

    try:
        return dict(SMS_SERVICES)[settings.SMS_PREFERRED_SERVICE]
    except KeyError:
        raise InvalidSMSService('Preferred SMS service "%s" not found' % settings.SMS_PREFERRED_SERVICE)
