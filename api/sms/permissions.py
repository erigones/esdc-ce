from api.permissions import DcBasePermission, check_security_data

__all__ = ('SmsSendPermission',)


class SmsSendPermission(DcBasePermission):
    """
    Allow send sms only if hash has been verified.
    """
    def has_permission(self, request, view, args, kwargs):
        return check_security_data(request, request.dc.settings.SMS_PRIVATE_KEY)  # default dc - dc1_settings
