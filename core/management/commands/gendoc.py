import os
import re
import shutil

from ._base import DanubeCloudCommand, CommandOption, CommandError, lcd


class Command(DanubeCloudCommand):
    help = 'Generate documentation files displayed in GUI.'
    DOC_REPO = 'https://github.com/erigones/esdc-docs.git'
    DOC_TMP_DIR = '/var/tmp/esdc-docs'
    options = (
        CommandOption('--api', '--api-only', action='store_true', dest='api_only', default=False,
                      help='Generate only the API documentation.'),
        CommandOption('--user-guide', '--user-guide-only', action='store_true', dest='user_guide_only', default=False,
                      help='Generate only the User Guide.'),
    )

    def gendoc_api(self):
        """Generate api documentation"""
        with lcd(self.PROJECT_DIR):
            doc_dir = self._path(self.PROJECT_DIR, 'doc', 'api')
            doc_dst = self._path(self.PROJECT_DIR, 'api', 'static', 'api', 'doc')
            bin_dst = self._path(self.PROJECT_DIR, 'api', 'static', 'api', 'bin')

            # Build sphinx docs
            with lcd(doc_dir):
                self.local('make esdc-clean; make esdc ESDOCDIR="%s"' % doc_dst)

            # Create es script suitable for download
            es_src = self._path(self.PROJECT_DIR, 'bin', 'es')
            es_dst = self._path(bin_dst, 'es')
            es_current = os.path.join(self.settings.PROJECT_DIR, 'var', 'www', 'static', 'api', 'bin', 'es')
            api_url = "API_URL = '%s'" % (self.settings.SITE_LINK + '/api')

            if os.path.isfile(es_current):
                with open(es_current, 'r') as es0:
                    for line in es0:
                        if line.startswith("API_URL = '"):
                            api_url = line
                            break

            with open(es_src) as es1:
                with os.fdopen(os.open(es_dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644), 'w') as es2:
                    es2.write(es1.read().replace("API_URL = 'http://127.0.0.1:8000/api'", api_url))

            # Copy es_bash_completion.sh to download location
            es_bc_src = self._path(doc_dir, 'es_bash_completion.sh')
            self.local('cp %s %s' % (es_bc_src, bin_dst))

        self.display('API documentation built successfully.', color='green')

    def gendoc_user_guide(self, fallback_branch='master'):
        """Generate user guide"""
        doc_dst = self._path(self.PROJECT_DIR, 'gui', 'static', 'user-guide')

        with lcd(self.PROJECT_DIR):
            try:
                branch = self.get_git_version()[0]  # Git tag or branch name
            except CommandError:
                self.display('Could not determine our branch or tag', color='yellow')
                branch = fallback_branch
                self.display('Falling back to "%s" branch' % branch, color='yellow')
            else:
                self.display('We are on branch "%s"' % branch)

        if self._path_exists(self.DOC_TMP_DIR, 'user-guide', 'conf.py'):
            existing_repo = True
            self.display('%s already exists in %s' % (self.DOC_REPO, self.DOC_TMP_DIR), color='yellow')
            with lcd(self.DOC_TMP_DIR):
                self.local('git fetch')
            self.display('%s has been successfully updated.' % self.DOC_REPO, color='green')
        else:
            if self._path_exists(self.DOC_TMP_DIR):
                self.display('Removing stale %s', self.DOC_TMP_DIR, color='yellow')
                shutil.rmtree(self.DOC_TMP_DIR)

            existing_repo = False
            self.local('git clone %s %s' % (self.DOC_REPO, self.DOC_TMP_DIR))
            self.display('%s has been successfully cloned.' % self.DOC_TMP_DIR, color='green')

        with lcd(self.DOC_TMP_DIR):
            if self.local('git checkout %s' % branch, raise_on_error=False) != 0:
                self.display('Could not checkout esdc-docs branch "%s"' % branch, color='yellow')
                branch = fallback_branch
                self.display('Falling back to "%s" branch' % branch, color='yellow')
                self.local('git checkout %s' % branch)

            self.display('Checked out esdc-docs branch "%s"' % branch, color='green')
            # If the branch is no a tag name, then we need to merge/pull
            if existing_repo and not re.search('^v[0-9]', branch):
                self.local('git merge --ff-only origin/%s' % branch)
                self.display('Merged esdc-docs branch "%s"' % branch, color='green')

        # Build sphinx docs
        with lcd(self._path(self.DOC_TMP_DIR, 'user-guide')):
            self.local('make esdc-clean; make esdc ESDOCDIR="%s"' % doc_dst)

        self.display('User guide built successfully.', color='green')

    def handle(self, api_only=False, user_guide_only=False, **options):
        if api_only and user_guide_only:
            pass
        elif api_only:
            self.gendoc_api()
            return
        elif user_guide_only:
            self.gendoc_user_guide()
            return

        self.gendoc_api()
        self.display('\n\n', stderr=True)
        self.gendoc_user_guide()
