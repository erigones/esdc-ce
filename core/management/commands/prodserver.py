from ._base import DanubeCloudCommand, CommandOption, lcd


class Command(DanubeCloudCommand):
    default_config_file = DanubeCloudCommand._path(DanubeCloudCommand.PROJECT_DIR, 'core', 'gunicorn-sio.py')
    help = 'Runs a production server (Gunicorn).'
    options = (
        CommandOption('-c', '--config', action='store', dest='config', default=default_config_file,
                      help='The Gunicorn config file. [%s]' % default_config_file),
    )

    def handle(self, *args, **options):
        with lcd(self.PROJECT_DIR):
            self.local('gunicorn -c %s core.wsgi:application' % options['config'], echo_command=True)
