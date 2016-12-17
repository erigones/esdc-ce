import logging

from django.conf import settings


def get_version():
    from core.version import __version__
    from core.version import __edition__

    return __edition__ + ':' + __version__


def setup_server_software():
    import gunicorn
    gunicorn.SERVER_SOFTWARE = 'Esdc/' + get_version()
    del gunicorn


class RequireEmailAdmins(logging.Filter):
    def filter(self, record):
        return settings.EMAIL_ADMINS
