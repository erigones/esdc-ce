from ._base import DanubeCloudCommand, lcd, CommandOption


class Command(DanubeCloudCommand):
    help = 'Shortcut for pip uninstall within the application\'s virtual environment.'
    option_list = (
        CommandOption('--library', action='store', dest='library', default='',
                      help='Library to be uninstalled from the virtual environment'),
    )

    def pip_uninstall(self, library, params='-y'):
        self.local('pip uninstall %s %s' % (params, library))
        self.display('%s have been successfully uninstalled.\n\n ' % library, color='green')

    def handle(self, **options):
        with lcd(self.PROJECT_DIR):
            self.pip_uninstall(options['library'])
