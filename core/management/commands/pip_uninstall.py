from ._base import DanubeCloudCommand, lcd, CommandOption


class Command(DanubeCloudCommand):
    help = 'Shortcut for pip uninstall within the application\'s virtual environment.'
    option_list = (
        CommandOption('-p', '--package', action='store', dest='package', default='',
                      help='Package to be uninstalled from the virtual environment'),
        CommandOption('-s', '--silence-errors', action='store_true', dest='silence_errors', default=False,
                      help='Do not propagate pip errors.'),
    )

    def pip_uninstall(self, package, raise_on_error, params='-y'):
        erroneous_return_code = self.local('pip uninstall %s %s' % (params, package), raise_on_error=raise_on_error)
        if erroneous_return_code:
            self.display('An error has occured while uninstalling %s!\n\n ' % package, color='red')
            if not raise_on_error:
                self.display('The library may be uninstalled already, we suppress the error.\n', color='magenta')
        else:
            self.display('%s have been successfully uninstalled.\n\n ' % package, color='green')

    def handle(self, **options):
        with lcd(self.PROJECT_DIR):
            self.pip_uninstall(options['package'], raise_on_error=not options['silence_errors'])
