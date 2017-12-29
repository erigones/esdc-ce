class SMSError(Exception):
    """
    Base SMS error.
    """
    pass


class InvalidSMSService(SMSError):
    pass


class InvalidSMSInput(SMSError, ValueError):
    pass


class SMSDisabled(SMSError):
    pass


class SMSSendFailed(SMSError):
    pass
