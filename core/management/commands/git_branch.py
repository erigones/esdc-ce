from ._base import DanubeCloudCommand, CommandOption, lcd


class Command(DanubeCloudCommand):
    help = 'Switch to git branch or tag.'
    options = (
        CommandOption('-t', '--tag', action='store', dest='branch', default=DanubeCloudCommand.DEFAULT_BRANCH,
                      help='Switch repositories to specific tag.'),
        CommandOption('-b', '--branch', action='store', dest='branch', default=DanubeCloudCommand.DEFAULT_BRANCH,
                      help='Switch repositories to specific branch.'),
    )
    BUILD_PLANS = getattr(DanubeCloudCommand.settings, 'ERIGONES_BUILD_PLANS', {})

    def git_branch(self, app, branch):
        """Helper function for switching into a branch in an repository"""
        if app == self.PROJECT_NAME:
            app_path = self.PROJECT_DIR
        else:
            raise ValueError('Unknown app')

        with lcd(app_path):
            self.local('git pull && git checkout %s' % branch)

        self.display('%s has been successfully switched to tag/branch %s.' % (app, branch), color='green')

    def switch_branch(self, branch):
        try:
            real_branch = self.BUILD_PLANS[self.PROJECT_NAME][branch]
        except KeyError:
            real_branch = branch

        self.git_branch(self.PROJECT_NAME, real_branch)

    def handle(self, *args, **options):
        branch = options.get('branch', self.DEFAULT_BRANCH)
        self.switch_branch(branch)
