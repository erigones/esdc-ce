from ._base import DanubeCloudCommand, CommandError, lcd


class Command(DanubeCloudCommand):
    help = 'Create git version tag.'
    args = '<name> [description]'
    name = ''
    desc = ''

    def git_tag(self, app, git_path):
        with lcd(git_path):
            self.local('git tag -a %s -s -m \'%s\'' % (self.name, self.desc))
            self.local('git push --tags')

        self.display('%s has been successfully tagged (%s).\n\n' % (app, self.name), color='green')

    def handle(self, name, *args, **options):
        self.name = name
        self.desc = ' '.join(args)

        if not (len(name) > 1 and name[0] == 'v' and name[1].isdigit()):
            raise CommandError('Tag name has to start with: v and number, e.g. v2.0.0')

        self.managepy('git_update')  # Update project and all apps
        from core.version import __version__

        if __version__ != name[1:]:
            if not self.confirm('Tag "%s" does not match __version__ ("%s") in version.py.\n'
                                'Are you sure you want to continue?' % (name, __version__)):
                raise CommandError('Invalid tag')

        self.git_tag(self.PROJECT_NAME, self.PROJECT_DIR)
