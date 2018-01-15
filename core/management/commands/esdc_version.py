from ._base import DanubeCloudCommand, CommandOption


class Command(DanubeCloudCommand):
    help = 'Display Danube Cloud version.'

    options = (
        CommandOption('-f', '--full', action='store_true', dest='full', default=False,
                      help='Display full version string (including edition).'),
    )

    def handle(self, full=False, **options):
        from core.version import __version__, __edition__

        if full:
            version = '%s:%s' % (__edition__, __version__)
        else:
            version = __version__

        self.display(version)
