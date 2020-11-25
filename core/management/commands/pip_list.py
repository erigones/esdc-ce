from ._base import DanubeCloudCommand, CommandOption


class Command(DanubeCloudCommand):
    help = 'Display installed python dependencies.'
    default_verbosity = 2

    def add_arguments(self, parser):
        parser.add_argument('-o', '--outdated',
                            action='store_true',
                            dest='outdated',
                            default=False, help='Display outdated python dependencies.')

    def handle(self, outdated=False, **options):
        if outdated:
            params = '-o'
        else:
            params = ''

        self.local('pip list %s' % params)
