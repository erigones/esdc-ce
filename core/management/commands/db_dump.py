from django.db import DEFAULT_DB_ALIAS

from ._base import DanubeCloudCommand, CommandError, CommandOption


class Command(DanubeCloudCommand):
    args = '[DB name]'
    help = 'Create database dump.'
    default_verbosity = 2
    options = (
        CommandOption('-d', '--database', action='store', dest='database',
                      help='Nominates a specific database to dump. Defaults to the "default" database.'),
        CommandOption('-a', '--data-only', action='store_true', dest='data_only', default=False,
                      help='Dump only the data, not the schema.'),
        CommandOption('-s', '--schema-only', action='store_true', dest='schema_only', default=False,
                      help='Dump only the schema, no data.'),
        CommandOption('-i', '--inserts', action='store_true', dest='inserts', default=False,
                      help='Dump data as INSERT commands with column names.'),
    )

    def handle(self, db_name=DEFAULT_DB_ALIAS, data_only=False, schema_only=False, inserts=False, **options):
        db_name = options.get('database') or db_name

        try:
            db = self.settings.DATABASES[db_name]
        except KeyError:
            raise CommandError('Invalid database name!')

        cmd = 'PGPASSWORD="%(PASSWORD)s" pg_dump -U %(USER)s -h %(HOST)s -p %(PORT)s -d %(NAME)s' % db

        if schema_only and data_only:
            pass
        elif schema_only:
            cmd += ' -s'
        elif data_only:
            cmd += ' -a'

        if inserts:
            cmd += ' --inserts'

        self.local(cmd, stderr_to_stdout=False)
