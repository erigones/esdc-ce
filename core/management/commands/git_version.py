from ._base import DanubeCloudCommand, lcd


class Command(DanubeCloudCommand):
    help = 'Display last git commit hash.'
    cmd_sha = 'git log --pretty=oneline -1 | cut -d " " -f 1'
    cmd_tag = 'git symbolic-ref -q HEAD || git describe --tags --exact-match'
    default_verbosity = 2

    def _get_version(self, appdir):
        with lcd(appdir):
            _tag = self.local(self.cmd_tag, capture=True).strip().split('/')[-1]
            _sha = self.local(self.cmd_sha, capture=True).strip()

        return '%s/%s' % (_tag, _sha)

    def handle(self, *args, **options):
        self.display('%s: %s' % (self.PROJECT_NAME, self._get_version(self.PROJECT_DIR)))
