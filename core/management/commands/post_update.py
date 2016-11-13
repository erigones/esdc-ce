from ._base import DanubeCloudCommand


class Command(DanubeCloudCommand):
    help = 'Post update stuff. Run after every update.'

    def handle(self, *args, **options):
        pass
