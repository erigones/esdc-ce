from ._base import DanubeCloudCommand, lcd


class Command(DanubeCloudCommand):
    help = 'Uninstall dependencies according to *etc/requirements-remove.txt*.'

    def pip_uninstall(self, req_rem_path, params='-y'):
        if self._path_exists(req_rem_path):
            self.local('pip uninstall %s -r %s' % (params, req_rem_path))
            self.display('%s have been successfully uninstalled.\n\n ' % req_rem_path, color='green')

    def handle(self, *args, **options):
        with lcd(self.PROJECT_DIR):
            self.pip_uninstall(self._path(self.PROJECT_DIR, 'etc', 'requirements-remove.txt'))
