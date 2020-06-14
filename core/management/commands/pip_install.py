from ._base import DanubeCloudCommand, CommandOption, lcd
import os
import re

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
        if os.uname()[0] == 'SunOS':
            params += ' --global-option=build_ext --global-option="-I%s/include/sunos/"' % self.erigones_home
            # if the pkgin-version-specific file exists and is readable, use this instead of the default one
            try:
                pkgin_conf = '/opt/local/etc/pkgin/repositories.conf'
                pkgin_ver = ''
                with open(pkgin_conf, 'r') as cf:
                    for line in cf:
                        if re.search('^http.*pkgsrc.joyent.com', line):
                            pkgin_ver = re.split('/', line)[5]

                new_req_file_both = DanubeCloudCommand._path('%s-%s' % (self.req_file_both, pkgin_ver))
                with open(new_req_file_both, 'r') as f:
                    if f.read():
                        self.req_file_both = new_req_file_both
            except Exception:
                # if anything goes wrong (e.g. version specific file or pkgin conf doesn't exist),
                # just don't override default requirements file and continue normal way
                pass

        # else: # non-SunOs system (not currently needed)
        #    params+=' --global-option=build_ext --global-option="-I%s/include/linux/"' % self.erigones_home

        with lcd(self.PROJECT_DIR):
            self.pip_install(self.req_file_both, params=params)

        if que_only:
            self.pip_install(self.req_file_node, params=params)
        else:
            self.pip_install(self.req_file_mgmt, params=params)
