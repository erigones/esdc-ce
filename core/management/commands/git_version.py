from ._base import DanubeCloudCommand


class Command(DanubeCloudCommand):
    help = 'Display last git commit hash.'
    default_verbosity = 2

    def handle(self, *args, **options):
        version = '%s/%s' % self.get_git_version()
        self.display('%s: %s' % (self.PROJECT_NAME, version))
