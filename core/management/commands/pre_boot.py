from ._base import DanubeCloudCommand


class Command(DanubeCloudCommand):
    help = 'Prepare application for startup.'

    def handle(self, *args, **options):
        pass
