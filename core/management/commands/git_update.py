from ._base import DanubeCloudCommand, lcd


class Command(DanubeCloudCommand):
    help = 'Update project from git repository.'

    def git_pull(self, git_dir, name):
        with lcd(git_dir):
            self.local('git pull')
            self.display('%s has been successfully updated.\n\n' % name, color='green')

    def handle(self, *args, **options):
        self.git_pull(self.PROJECT_DIR, self.PROJECT_NAME)
