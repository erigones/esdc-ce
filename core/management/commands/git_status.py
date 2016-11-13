from ._base import DanubeCloudCommand, lcd


class Command(DanubeCloudCommand):
    help = 'Show git status.'

    def git_status(self, git_dir, name):
        with lcd(git_dir):
            if not self.verbose:
                self.display('-- %s --' % name, color='blue')
            self.local('git status')
            self.display('--\n\n', stderr=True)

    def handle(self, *args, **options):
        self.git_status(self.PROJECT_DIR, self.PROJECT_NAME)
