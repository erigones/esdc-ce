from ._base import DanubeCloudCommand, CommandOption, lcd
import os

PROJECT_DIR = DanubeCloudCommand.PROJECT_DIR


class Command(DanubeCloudCommand):
    help = 'Install or update dependencies according to *etc/requirements-<type>.txt*.'
    options = (
        CommandOption('-q', '--que', '--node', action='store_true', dest='que_only', default=False,
                      help='Install or update compute node related requirements.'),
        CommandOption('-u', '--update', action='store_true', dest='update', default=False,
                      help='Update installed requirements.'),
    )
    req_file_both = DanubeCloudCommand._path(PROJECT_DIR, 'etc', 'requirements-both.txt')
    req_file_mgmt = DanubeCloudCommand._path(PROJECT_DIR, 'etc', 'requirements-mgmt.txt')
    req_file_node = DanubeCloudCommand._path(PROJECT_DIR, 'etc', 'requirements-node.txt')
    erigones_home = os.path.abspath(os.environ.get('ERIGONES_HOME', '/opt/erigones'))

    def pip_install(self, req_path, params=''):
        if self._path_exists(req_path):
            self.local('pip install --no-cache-dir --disable-pip-version-check %s -r %s' % (params, req_path))
            self.display('%s have been successfully installed.\n\n ' % req_path, color='green')

    def pip_update_pip(self):
        self.local('pip install -U pip')
        self.display('pip has been successfully updated.\n\n ', color='green')

    def handle(self, update=False, que_only=False, **options):
        # Always update pip first
        self.pip_update_pip()

        if update:
            params = '-U'
        else:
            params = ''

        # add include dir for pip builds
        if que_only:
            params+=' --global-option=build_ext --global-option="-I%s/include/sunos/"' % self.erigones_home
        # not currently needed
        #else:
        #    params+=' --global-option=build_ext --global-option="-I%s/include/centos/"' % self.erigones_home

        with lcd(self.PROJECT_DIR):
            self.pip_install(self.req_file_both, params=params)

        if que_only:
            self.pip_install(self.req_file_node, params=params)
        else:
            self.pip_install(self.req_file_mgmt, params=params)
