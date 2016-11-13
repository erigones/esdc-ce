import os

from ._base import DanubeCloudCommand, lcd


class Command(DanubeCloudCommand):
    help = 'Install Erigones specific patches for 3rd party applications in envs directory.'

    def handle(self, *args, **options):
        patches = []
        patches_dir = os.path.join(self.PROJECT_DIR, 'etc', 'patch_envs')

        if os.path.isdir(patches_dir):
            patches = os.listdir(patches_dir)

        import django
        envs_lib_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(django.__file__)), '..'))

        with lcd(envs_lib_dir):
            for patch in patches:
                self.display('Installing patch: %s' % patch, color='white')
                rc = self.local('patch -N -t -p0 -i ' + os.path.join(patches_dir, patch), raise_on_error=False)

                if rc == 0:
                    self.display('Patch %s was successfully installed\n\n' % patch, color='green')
                else:
                    self.display('Failed to install patch %s\n\n' % patch, color='yellow')
