from compileall import compile_dir

from ._base import DanubeCloudCommand


class Command(DanubeCloudCommand):
    help = 'Recursively byte=compile all modules in ERIGONES_HOME.'

    def handle(self, *args, **options):
        self.display('Byte-compiling all modules in %s' % self.PROJECT_DIR, color='white')
        quiet = int(int(options.get('verbosity', self.default_verbosity)) <= self.default_verbosity)
        rc = compile_dir(self.PROJECT_DIR, maxlevels=20, quiet=quiet)

        if rc == 0:
            self.display('Byte-compiled all modules in %s' % self.PROJECT_DIR, color='green')
        else:
            self.display('Error while byte-compiling some modules in %s' % self.PROJECT_DIR, color='red')
