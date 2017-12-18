import json
import socket

COMMANDS = (
    'qmp_capabilities',
    'cont',
    'stop',
    'migrate',
    'migrate-cancel',
    'query-migrate',
    'query-status',
    'is-running',
)


class QMPError(Exception):
    pass


class QMP(object):
    """
    QEMU Machine Protocol.
    """
    info = None
    _socket = None
    _socket_file = None
    TIMEOUT = 30

    def __init__(self, address):
        self._socket_address = address

    def _json_read(self):
        res = self._socket_file.readline().strip()

        if not res:
            return None

        try:
            response = json.loads(res)
        except Exception:
            raise QMPError('Failed to parse JSON message: %s' % res)

        if response:
            if 'error' in response:
                raise QMPError(response['error'].get('desc', response['error']))

            if 'return' in response:
                return response['return']
            else:
                return response
        else:
            return None

    def _json_cmd(self, request, timeout=TIMEOUT):
        try:
            req = json.dumps(request)
        except Exception:
            raise QMPError('Failed to create JSON payload: %s' % request)

        self._socket.settimeout(timeout)
        self._socket.sendall(req)

        return self._json_read()

    def connect(self, timeout=TIMEOUT, read_greeting=False):
        if isinstance(self._socket_address, tuple):
            family = socket.AF_INET
        else:
            family = socket.AF_UNIX

        # noinspection PyArgumentEqualDefault
        self._socket = socket.socket(family=family, type=socket.SOCK_STREAM)
        self._socket.settimeout(timeout)
        self._socket.connect(self._socket_address)
        self._socket_file = self._socket.makefile()

        if read_greeting:
            return self._json_read()

    def close(self):
        self._socket_file.close()
        self._socket.close()

    def execute(self, cmd, arguments=None, **kwargs):
        execmd = {'execute': cmd}

        if arguments is not None:
            execmd['arguments'] = arguments

        return self._json_cmd(execmd, **kwargs)


class QMPClient(object):
    """
    QMP Client.
    """
    TIMEOUT = 3

    def __init__(self, socket_path, timeout=TIMEOUT, init=False):
        self._qmp = QMP(socket_path)
        greeting = self._qmp.connect(timeout=timeout, read_greeting=True)

        if not greeting or 'QMP' not in greeting:
            raise QMPError('Connection error')

        if init:
            self.qmp_capabilities()

    def __enter__(self):
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._qmp.close()

    def _execute(self, cmd, **kwargs):
        return self._qmp.execute(cmd, **kwargs)

    def qmp_capabilities(self):
        return self._execute('qmp_capabilities')

    def cont(self):
        return self._execute('cont')

    def stop(self):
        return self._execute('stop')

    def migrate(self, destination_uri, maximum_downtime=0.5):
        self._execute('migrate_set_downtime', arguments={'value': maximum_downtime})

        return self._execute('migrate', arguments={'uri': destination_uri})

    def migrate_cancel(self):
        return self._execute('migrate_cancel')

    def query_migrate(self):
        return self._execute('query-migrate').get('status', '')

    def query_status(self):
        return self._execute('query-status')

    def is_running(self):
        res = self.query_status().get('running', False)

        if not res:
            raise QMPError(str(res))

        return res
