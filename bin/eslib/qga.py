import socket
import random

from . import PY3
from .qmp import QMPError, QMP

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


class QGAError(Exception):
    pass


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
