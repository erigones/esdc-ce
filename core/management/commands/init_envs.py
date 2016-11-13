from ._base import DanubeCloudCommand, CommandError


class Command(DanubeCloudCommand):
    help = 'Initialize the virtual environments.'

    def handle(self, *args, **options):
        raise CommandError('Use ctl.sh directly')
