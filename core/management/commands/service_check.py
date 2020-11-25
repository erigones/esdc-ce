from ._base import DanubeCloudCommand, CommandOption, CommandError


class Command(DanubeCloudCommand):
    help = 'Check connection to internal/admin services.'

    def add_arguments(self, parser):
        parser.add_argument('-q', '--que', '--node',
                            action='store_true',
                            dest='que_only',
                            default=False,
                            help='Check only services related to erigonesd on a compute node.')

    def _ok(self, ssl_on):
        if ssl_on:
            return self.colors.green('OK') + ' (SSL)'
        else:
            return self.colors.yellow('OK') + ' (no SSL)'

    def _failed(self):
        return self.colors.red('FAILED')

    def check_rabbitmq(self):
        from que.erigonesd import cq
        con = cq.broker_connection()

        try:
            con.connect().send_heartbeat()
        except Exception as exc:
            self.display('RabbitMQ connection [{}]: {} ({})'.format(con.as_uri(), self._failed(), exc))
            return False
        else:
            self.display('RabbitMQ connection [{}]: {}'.format(con.as_uri(), self._ok(con.ssl)))
            return True

    def check_redis(self):
        from que.erigonesd import cq
        con = cq.backend

        try:
            con.client.ping()
        except Exception as exc:
            self.display('Redis connection [{}]: {} ({})'.format(con.as_uri(), self._failed(), exc))
            return False
        else:
            ssl = 'SSLConnection' in repr(con.client)
            self.display('Redis connection [{}]: {}'.format(con.as_uri(), self._ok(ssl)))
            return True

    def check_db(self):
        from django.db import connections
        res = []

        for db_name in connections:
            con = connections[db_name]

            try:
                con.connect()
            except Exception as exc:
                self.display('Database "{}" connection: {} ({})'.format(db_name, self._failed(), exc))
                res.append(False)
            else:
                self.display('Database "{}" connection [{}]: {}'.format(db_name, con.connection.dsn, self._ok(False)))
                res.append(True)

        return res

    def handle(self, que_only=False, **options):
        result = [self.check_redis(), self.check_rabbitmq()]

        if not que_only:
            result.extend(self.check_db())

        if not all(result):
            raise CommandError('Test connection to some services has failed')
