from collections import namedtuple, OrderedDict
from subprocess import Popen, PIPE, STDOUT
from threading import Thread
from logging import getLogger
from time import sleep
from django.conf import settings

from api.exceptions import GatewayTimeout
from api.request import Request as APIRequest
from api.system.service.events import SystemReloaded
from que.utils import worker_command

logger = getLogger(__name__)

Service = namedtuple('Service', ('name', 'desc', 'os_services'))


class _ServiceControl(object):
    """
    Danube Cloud service control base class.
    """
    START = 'start'
    STOP = 'stop'
    RESTART = 'restart'
    RELOAD = 'reload'
    STATUS = 'status'

    _services = ()

    def __init__(self, services=None):
        if services is None:
            self.services = OrderedDict((i.name, i) for i in self._services)
        else:
            self.services = OrderedDict((i.name, i) for i in self._services if i.name in services)

    def _execute_cmd(self, cmd, **kwargs):
        """Execute a command in the shell and return a dict with returncode, stdout and stderr items."""
        raise NotImplementedError

    def _action_cmd(self, service, action, command):
        """Execute and parse service command output"""
        assert service in self.services, 'Service with name "%s" is not defined' % service

        srv = self.services[service]
        codes = []
        details = []

        for os_service in srv.os_services:
            reply = self._execute_cmd(command, service=os_service, action=action)

            if 'returncode' in reply:
                rc = reply['returncode']
                msg = reply.get('stderr', '') or reply.get('stdout', '')
            else:
                rc = 111
                msg = str(reply)

            codes.append(rc)
            details.append(msg)

        is_ok = sum(codes) == 0
        res = {'ok': is_ok, 'desc': srv.desc, 'name': srv.name, 'details': details}

        if not is_ok:
            res['error_code'] = '-'.join(map(str, codes))

        return res

    def _service_cmd(self, service, action):
        """Service command"""
        raise NotImplementedError

    def start(self, service):
        """Start service"""
        logger.warn('Starting service %s', service)
        return self._service_cmd(service, self.START)

    def stop(self, service):
        """Stop service"""
        logger.warn('Stopping service %s', service)
        return self._service_cmd(service, self.STOP)

    def restart(self, service):
        """Restart service"""
        logger.warn('Restarting service %s', service)
        return self._service_cmd(service, self.RESTART)

    def reload(self, service):
        """Reload service"""
        logger.warn('Reloading service %s', service)
        return self._service_cmd(service, self.RELOAD)

    def status(self, service):
        """Check service status"""
        return self._service_cmd(service, self.STATUS)

    def status_all(self):
        """Return status of all services"""
        return [self.status(service) for service in self.services]


class ServiceControl(_ServiceControl):
    """
    Danube Cloud mgmt service control panel.
    """
    _services = (
        Service('db', 'Database', ('postgresql-9.5', 'pgbouncer')),
        Service('mq', 'Message queue', ('rabbitmq-server',)),
        Service('cache', 'Cache', ('redis',)),
        Service('vnc', 'Remote console manager', ('tomcat', 'guacd')),
        Service('web-proxy', 'Web proxy', ('haproxy',)),
        Service('web-static', 'Web static', ('nginx',)),
        Service('app-sio', 'Socket.io application server', ('esdc@gunicorn-sio',)),
        Service('app-api', 'API application server', ('esdc@gunicorn-api',)),
        Service('app-gui', 'GUI application server', ('esdc@gunicorn-gui',)),
        Service('erigonesd:mgmt', 'Erigonesd mgmt worker', ('erigonesd',)),
        Service('erigonesd:beat', 'Erigonesd task scheduler', ('erigonesd-beat',)),
    )
    app_services = ('app-sio', 'app-api', 'app-gui', 'erigonesd:mgmt')

    def _execute_cmd(self, cmd, **kwargs):
        """Execute a command in the shell and return a command result"""
        cmd = cmd.format(**kwargs)
        logger.debug('Running command: "%s"', cmd)
        p = Popen(cmd, shell=True, bufsize=0, close_fds=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
        stdout, _ = p.communicate()

        return {
            'returncode': p.returncode,
            'stdout': stdout,
            'stderr': '',
        }

    def _service_cmd(self, service, action):
        """Service command"""
        return self._action_cmd(service, action, 'sudo /usr/bin/systemctl {action} {service}')


class NodeServiceControl(_ServiceControl):
    """
    Danube Cloud compute node service control panel.
    """
    START = 'enable'
    STOP = 'disable'
    RELOAD = 'refresh'

    _services = (
        Service('erigonesd:fast', 'Erigonesd compute node "fast" worker', ('erigonesd:fast',)),
        Service('erigonesd:slow', 'Erigonesd compute node "slow" worker', ('erigonesd:slow',)),
        Service('erigonesd:image', 'Erigonesd compute node "image" worker', ('erigonesd:image',)),
        Service('erigonesd:backup', 'Erigonesd compute node "backup" worker', ('erigonesd:backup',)),
    )
    app_services = ('erigonesd:fast', 'erigonesd:slow', 'erigonesd:image', 'erigonesd:backup')

    def __init__(self, node, **kwargs):
        self.node = node
        super(NodeServiceControl, self).__init__(**kwargs)

    def _execute_cmd(self, cmd, **kwargs):
        """Run a worker panel command and return the command dict"""
        cmd = cmd.format(**kwargs)
        worker = self.node.worker('fast')
        reply = worker_command('execute', worker, cmd=cmd.split())

        if reply is None:
            raise GatewayTimeout('Node worker is not responding')

        return reply

    def _service_cmd(self, service, action):
        """Service command"""
        if action == 'status':
            cmd = '/usr/bin/svcs -pvH {service}'
        else:
            cmd = '/usr/sbin/svcadm {action} {service}'

        return self._action_cmd(service, action, cmd)


class SystemReloadThread(Thread):
    """
    Reload all app services in background.
    It is important to restart/reload the calling service as last one.
    Used by eslic.
    """
    daemon = True

    def __init__(self, delay=3, task_id=None, request=None, reason=''):
        self.delay = delay
        self.task_id = task_id
        self.request = request
        self.reason = reason
        self.last_service = self._get_last_service(self.request)
        self.sctrl = ServiceControl()
        super(SystemReloadThread, self).__init__(name='system-reload-thread')

    @staticmethod
    def _get_last_service(request):
        if request:
            if isinstance(request, APIRequest):
                return 'app-api'
            else:
                return 'app-gui'
        return 'erigonesd:mgmt'

    def reload_service(self, name):
        # Issue esdc-ce#20
        self.sctrl.restart(name)

    def reload_all(self):
        last = None

        for name in self.sctrl.app_services:
            if name == self.last_service:
                last = name
            else:
                self.reload_service(name)

        if last:
            self.reload_service(last)

    def run(self):
        logger.info('Initializing system reload')
        sleep(self.delay)

        if settings.DEBUG:
            logger.info('Skipping system reload in DEBUG mode')
        else:
            self.reload_all()
            logger.info('System reloaded')

        if self.task_id:
            SystemReloaded(self.task_id, request=self.request, reason=self.reason).send()
