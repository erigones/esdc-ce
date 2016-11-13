import os

from django.apps import apps as django_apps

from ._base import lcd, DanubeCloudCommand, CommandOption, CommandError


class Command(DanubeCloudCommand):
    help = 'Synchronize DB with models by running all Django migrations.'
    options = (
        CommandOption('-f', '--force', action='store_true', dest='force', default=False,
                      help='Skip confirmation dialog.'),
        CommandOption('-i', '--init', action='store_true', dest='init', default=False,
                      help='Initialize empty database.'),
        CommandOption('-t', '--test', action='store_true', dest='test', default=False,
                      help='Synchronize the test database.'),
    )

    def drop_useless_indexes(self):
        """Django creates lots of indexes by default"""
        from django.db import connection
        c = connection.cursor()
        c.execute("SELECT tablename, indexname from pg_indexes WHERE "
                  "schemaname='public' AND indexname ~ '_(uu)?id_[a-z0-9]+_like$'")
        indexes = c.fetchall()

        if indexes:
            self.display('Going to DROP %d useless DB indexes' % (len(indexes)), color='blue')

            for table, idx in indexes:
                self.display('Dropping useless index "%s" from table "%s"' % (idx, table))
                c.execute('DROP INDEX %s' % idx)

    def handle(self, force=False, init=False, test=False, **options):
        if not force and not self.confirm('Are you sure you want to load DB migrations?'):
            self.display('Not running migrations.', color='yellow')
            return

        from django.db import connection
        if init and connection.introspection.table_names():
            raise CommandError('The database is not empty!')

        kwargs = {}

        if test:
            kwargs['settings'] = 'core.tests.test_settings'

        fixtures = []

        for app in django_apps.get_app_configs():
            fixture_path = os.path.join(app.path, 'fixtures')

            if not os.path.isdir(fixture_path):
                continue

            if app.name == 'pdns':
                db = 'pdns'
            else:
                db = 'default'

            for fixture in os.listdir(fixture_path):
                if fixture.startswith('init'):
                    fixtures.append((db, os.path.join(fixture_path, fixture)))

        migrate_cmd = ['migrate', '--no-initial-data']

        if force:
            migrate_cmd.append('--noinput')

        with lcd(self.PROJECT_DIR):
            self.display('Running DB migrations in "default" database', color='yellow')
            self.managepy(*migrate_cmd, database='default', **kwargs)
            self.display('Running DB migrations in "pdns" database', color='yellow')
            self.managepy(*migrate_cmd, database='pdns', **kwargs)
            self.drop_useless_indexes()  # Django creates lots of indexes by default
            self.display('DB has been synced - all app migrations have been installed.', color='green')

            if init:
                for db, fixture in fixtures:
                    self.display('Loading initial DB data into "%s" database from %s' % (db, fixture), color='yellow')
                    self.managepy('loaddata', fixture, database=db)
                self.display('Initial data has been loaded - the DB is ready to use.', color='green')
