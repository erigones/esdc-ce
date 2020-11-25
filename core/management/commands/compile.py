from compileall import compile_dir

from ._base import DanubeCloudCommand, CommandOption


class Command(DanubeCloudCommand):
    help = 'Recursively byte-compile all modules in ERIGONES_HOME.'

    def add_arguments(self, parser):
        parser.add_argument('-q', '--que', '--node',
                            action='store_true',
                            dest='que_only',
                            default=False,
                            help='Byte-compile only compute node related stuff.')

    def handle(self, que_only=False, **options):
        if que_only:
            target_folders = [self._path(self.PROJECT_DIR, i) for i in ('envs', 'core', 'que')]
        else:
            target_folders = [self.PROJECT_DIR]

        quiet = int(int(options.get('verbosity', self.default_verbosity)) <= self.default_verbosity)

        for folder in target_folders:
            self.display('Byte-compiling all modules in %s' % folder, color='white')
            rc = compile_dir(folder, maxlevels=20, quiet=quiet)

            if rc:
                self.display('Byte-compiled all modules in %s' % folder, color='green')
            else:
                self.display('Error while byte-compiling some modules in %s' % folder, color='yellow')
