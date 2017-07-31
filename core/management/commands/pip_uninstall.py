from ._base import DanubeCloudCommand, lcd, CommandOption


class Command(DanubeCloudCommand):
    help = 'Shortcut for pip uninstall within the application\'s virtual environment.'
    args = '<package1> <package2> ...'
    missing_args_message = ("No database fixture specified. Please provide the "
                            "path of at least one fixture in the command line.")
    option_list = (
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

    def handle(self, *packages, **options):
        if not packages:
            self.display('No packages selected for removal.')

        with lcd(self.PROJECT_DIR):
            for package in packages:
                self.pip_uninstall(package, raise_on_error=not options.get('silence_errors'))
