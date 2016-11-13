from ._base import DanubeCloudCommand, CommandOption, CommandError


class Command(DanubeCloudCommand):
    help = 'Install project and python dependencies and build a software package suitable for deployment.'
    options = (
        CommandOption('-q', '--que', '--node', action='store_true', dest='que_only', default=False,
                      help='Build only compute node related stuff.'),
    )

    def build(self, que_only=False):
        """Helper for the build and build_que commands"""
        ctlsh = self.ctlsh
        pip_install = ['pip_install', '--update']

        if que_only:
            pip_install.append('--node')
        elif self.local('uname -s', capture=True, raise_on_error=False).strip() == 'SunOS':
            raise CommandError('Running on compute node, did you forget to specify "--node"?')

        ctlsh(*pip_install)

        if not que_only:
            ctlsh('patch_envs')
            ctlsh('gendoc')
            ctlsh('collectstatic', '--noinput', '--clear')
            self.local('git checkout var/www/static/.gitignore', raise_on_error=False)
            ctlsh('compress', '--force')

    def handle(self, que_only=False, **options):
        self.build(que_only=que_only)
        self.display('Success.', color='green')
