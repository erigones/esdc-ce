import logging

from django.conf import settings

from gui.signals import allow_switch_company_profile

logger = logging.getLogger(__name__)


def user_profile_company_only_form(user):
    result = allow_switch_company_profile.send(sender='core.utils.user_profile_company_only_form', user=user)
    allow = False

    for signal_results in result:
        if signal_results[1]:
            allow = True

    return allow


def setup_server_software():
    from core.version import __version__
    import gunicorn
    gunicorn.SERVER_SOFTWARE = 'Esdc/' + __version__
    del gunicorn


class RequireEmailAdmins(logging.Filter):
    def filter(self, record):
        return settings.EMAIL_ADMINS
