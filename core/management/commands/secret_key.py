import os

from ._base import DanubeCloudCommand, CommandError


class Command(DanubeCloudCommand):
    help = 'Check the existence of SECRET_KEY in local_settings.py and generate one if needed.'

    def handle(self, *args, **options):
        try:
            from core import local_settings
        except ImportError:
            local_settings = None
            fn = self._path(self.PROJECT_DIR, 'core', 'local_settings.py')
        else:
            fn = local_settings.__file__.replace('local_settings.pyc', 'local_settings.py')

        try:
            # noinspection PyUnresolvedReferences
            key = local_settings.SECRET_KEY
        except AttributeError:
            self.display('Missing SECRET_KEY in local_settings.py', color='yellow')
            key = os.urandom(128).encode('base64')[:76]
            with open(fn, 'a') as f:
                f.write('\nSECRET_KEY="""' + key + '"""\n')
            self.display('New SECRET_KEY was saved in %s' % fn, color='green')

        if key:
            self.display('SECRET_KEY is OK', color='green')
        else:
            raise CommandError('SECRET_KEY is empty!')
