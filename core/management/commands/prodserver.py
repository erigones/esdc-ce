from ._base import DanubeCloudCommand, CommandOption, lcd


class Command(DanubeCloudCommand):
    default_config_file = DanubeCloudCommand._path(DanubeCloudCommand.PROJECT_DIR, 'core', 'gunicorn-sio.py')
    help = 'Runs a production server (Gunicorn).'

    def add_arguments(self, parser):
        parser.add_argument('-c', '--config',
                            action='store',
                            dest='config',
                            default=self.default_config_file,
                            help='The Gunicorn config file. [%s]' % self.default_config_file)

    def handle(self, *args, **options):
        with lcd(self.PROJECT_DIR):
            self.local('gunicorn -c %s core.wsgi:application' % options['config'], echo_command=True)
