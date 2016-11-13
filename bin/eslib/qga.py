import json
import socket
import random

from . import PY3

COMMANDS = (
    'fsfreeze',
    'info',
    'ping',
    'sync',
    'reboot',
    'poweroff',
    'get-time',
    'set-time',
)

if PY3:
    x_range = range
else:
    x_range = xrange


class QMPError(Exception):
    pass


class QGAError(Exception):
    pass


class QMP(object):
    """
    QEMU Machine Protocol.
    """
    _socket = None
    _socket_file = None
    TIMEOUT = 30

    def __init__(self, address):
        self._socket_address = address

    def _json_cmd(self, request, timeout=TIMEOUT):
        try:
            req = json.dumps(request)
        except Exception:
            raise QMPError('Failed to create JSON payload: %s' % request)

        self._socket.settimeout(timeout)
        self._socket.sendall(req)
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

            return response['return']
        else:
            return None

    def connect(self, timeout=TIMEOUT):
        if isinstance(self._socket_address, tuple):
            family = socket.AF_INET
        else:
            family = socket.AF_UNIX

        # noinspection PyArgumentEqualDefault
        self._socket = socket.socket(family=family, type=socket.SOCK_STREAM)
        self._socket.settimeout(timeout)
        self._socket.connect(self._socket_address)
        self._socket_file = self._socket.makefile()

    def close(self):
        self._socket_file.close()
        self._socket.close()

    def execute(self, cmd, arguments=None, **kwargs):
        execmd = {'execute': cmd}

        if arguments is not None:
            execmd['arguments'] = arguments

        return self._json_cmd(execmd, **kwargs)


class QGAClient(object):
    """
    Qemu Guest Agent Client
    """
    TIMEOUT = 3

    def __init__(self, socket_path, timeout=QMP.TIMEOUT):
        self._qmp = QMP(socket_path)
        self._qmp.connect(timeout=timeout)

    def __enter__(self):
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._qmp.close()

    def _execute(self, cmd, **kwargs):
        self.sync()

        return self._qmp.execute(cmd, **kwargs)

    def _shutdown(self, mode='powerdown'):
        if mode not in ('powerdown', 'reboot'):
            raise QMPError('Invalid shutdown mode')

        return self._execute('guest-shutdown', arguments={'mode': mode}, timeout=self.TIMEOUT)

    def close(self):
        self._qmp.close()

    def ping(self, timeout=TIMEOUT):
        try:
            res = not self._qmp.execute('guest-ping', timeout=timeout)
        except socket.timeout:
            res = False

        if not res:
            raise QGAError('Qemu guest agent down')

        return res

    def sync(self, timeout=TIMEOUT, attempts=16):
        self.ping()
        sid = int(random.getrandbits(16))

        for _ in x_range(attempts):
            x = self._qmp.execute('guest-sync', arguments={'id': sid}, timeout=timeout)

            if x == sid:
                return x
        else:
            raise QMPError('Could not sync with qemu guest agent after %d attempts' % attempts)

    def info(self, timeout=TIMEOUT):
        return self._execute('guest-info', timeout=timeout)

    def fsfreeze(self, subcmd):
        if subcmd in ('freeze', 'thaw'):
            self.sync(timeout=30)
            return self._qmp.execute('guest-fsfreeze-' + subcmd, timeout=120)
        elif subcmd == 'status':
            return self._execute('guest-fsfreeze-status')
        else:
            raise QMPError('Invalid fsfreeze subcommand')

    def poweroff(self):
        return self._shutdown(mode='powerdown')

    def reboot(self):
        return self._shutdown(mode='reboot')

    def get_time(self, timeout=TIMEOUT):
        return self._execute('guest-get-time', timeout=timeout)

    def set_time(self, time=None, timeout=TIMEOUT):
        if time is None:
            return self._execute('guest-set-time', timeout=timeout)
        else:
            return self._execute('guest-set-time', arguments={'time': int(time)}, timeout=timeout)
