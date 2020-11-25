from ._base import DanubeCloudCommand, CommandOption, CommandError


class Command(DanubeCloudCommand):
    help = 'Install project and python dependencies and build a software package suitable for deployment.'

    def add_arguments(self, parser):
        parser.add_argument('-q', '--que', '--node',
                            action='store_true',
                            dest='que_only',
                            default=False,
                            help='Build only compute node related stuff.')

    def build(self, que_only=False):
        """Helper for the build and build_que commands"""
        ctlsh = self.ctlsh
        pip_install = ['pip_install', '--update']
        compile_cmd = ['compile']

        if que_only:
            pip_install.append('--node')
            compile_cmd.append('--node')
        elif self.local('uname -s', capture=True, raise_on_error=False).strip() == 'SunOS':
            raise CommandError('Running on compute node, did you forget to specify "--node"?')

        ctlsh(*pip_install)
        ctlsh(*compile_cmd)
        ctlsh('patch_envs')

        if not que_only:
            ctlsh('gendoc')
            ctlsh('collectstatic', '--noinput', '--clear')
            self.local('git checkout var/www/static/.gitignore', raise_on_error=False)
            ctlsh('compress', '--force')

    def handle(self, que_only=False, **options):
        self.build(que_only=que_only)
        self.display('Success.', color='green')
