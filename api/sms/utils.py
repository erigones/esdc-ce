from vms.models import DefaultDc
# SMS services
# Must be imported this way and the views modules should have a sms_send function and PROVIDER_NAME constant
import api.sms.smsapi.views


SMS_SERVICES = (
    ('smsapi', api.sms.smsapi.views),
)


def get_services():
    """
    Returns list of SMS service providers which can be used as choices form field parameter.
    """
    return [(service, module.PROVIDER_NAME) for service, module in SMS_SERVICES]


def get_current_service(settings=None):
    """
    Function that list supported services for sending text messages.
    """
    if not settings:
        settings = DefaultDc().settings  # dc1_settings

    return dict(SMS_SERVICES)[settings.SMS_PREFERRED_SERVICE]
