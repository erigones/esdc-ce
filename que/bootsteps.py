from __future__ import absolute_import

import os
import json
from subprocess import PIPE, STDOUT
from threading import Thread
from logging import getLogger
from time import sleep

try:
    # noinspection PyCompatibility
    from Queue import Queue
except ImportError:
    # noinspection PyUnresolvedReferences,PyCompatibility
    from queue import Queue

from psutil import Popen, NoSuchProcess
from celery.bootsteps import StartStopStep
from frozendict import frozendict

from que import E_SHUTDOWN, Q_MGMT, Q_FAST

logger = getLogger(__name__)


class ESDCDaemon(StartStopStep):
    """
    A common boot step for all erigonesd services.
    """
    label = 'ESDCDaemon'
    requires = ('celery.worker.components:Pool',)

    def start(self, parent):
        logger.info('Starting %s on %s', self.label, parent.hostname)

    def stop(self, parent):
        logger.info('Stopping %s on %s', self.label, parent.hostname)
        logger.warn('%s is shutting down', parent.hostname)
        E_SHUTDOWN.set()


class _PeriodicTaskDaemon(StartStopStep):
    """
    An abstract boot step for building a daemon, which runs tasks in periodic interval.
    """
    _stopping = False
    _interval = 60
    _priority = 10

    def __init__(self, parent, **kwargs):
        super(_PeriodicTaskDaemon, self).__init__(parent, **kwargs)
        self._timer = parent.timer
        self._tref = None
        self._redis = parent.app.backend.client
        self._periodic_tasks = []

    def _periodic(self):
        for task in self._periodic_tasks:
            task()

    def start(self, parent):
        logger.info('Starting %s on %s', self.label, parent.hostname)
        self._tref = self._timer.call_repeatedly(self._interval, self._periodic, priority=self._priority)

    def stop(self, parent):
        logger.info('Stopping %s on %s', self.label, parent.hostname)
        self._stopping = True

        if self._tref:
            self._tref.cancel()
            self._tref = None


class FastDaemon(_PeriodicTaskDaemon):
    """
    Danube Cloud internal fast daemon - runs two threads for monitoring VM status changes.
    """
    label = 'FastDaemon'

    node_uuid = None
    vm_status_queue = None
    vm_status_watcher = None
    vm_status_dispatcher_thread = None
    vm_status_monitor_thread = None

    SYSEVENT = ('sysevent', '-j', '-c', 'com.sun:zones:status', 'status')
    VM_STATUS = frozendict({
        'running': 'running',
        'uninitialized': 'stopped'
    })

    def __init__(self, parent, **kwargs):
        hostname = parent.hostname
        self._conf = parent.app.conf
        self.enabled = self._conf.ERIGONES_FAST_DAEMON_ENABLED and hostname.startswith(Q_FAST + '@')
        super(FastDaemon, self).__init__(parent, **kwargs)

        if self.enabled:
            self._periodic_tasks.append(self._vm_status_thread_check)

    def _vm_status_dispatcher(self):
        """THREAD: Reads VM status changes from queue and creates a vm_status_event_cb task for every status change"""
        from que.utils import task_id_from_string, send_task_forever  # Circular imports

        vm_status_task = self._conf.ERIGONES_VM_STATUS_TASK
        task_user = self._conf.ERIGONES_TASK_USER
        queue = self.vm_status_queue
        logger.info('Emitting VM status changes on node %s via %s', self.node_uuid, vm_status_task)

        while True:
            event = queue.get()
            task_id = task_id_from_string(task_user)
            logger.info('Creating task %s for event: "%s"', task_id, event)
            # Create VM status task
            send_task_forever(self.label, vm_status_task, args=(event, task_id), queue=Q_MGMT, expires=None,
                              task_id=task_id)

    def _vm_status_monitor(self, sysevent_stdout):
        """THREAD: Reads line by line from sysevent process and puts relevant VM status changes into queue"""
        vm_status = self.VM_STATUS
        node_uuid = self.node_uuid
        queue = self.vm_status_queue
        logger.info('Monitoring VM status changes on node %s', node_uuid)

        for line in iter(sysevent_stdout.readline, ''):
            line = line.strip()

            try:
                event = json.loads(line)['data']
            except Exception as e:
                logger.critical('Could not parse (%s), sysevent line: "%s"', e, line)
                continue

            try:
                state = vm_status[event.get('newstate')]
            except KeyError:
                logger.debug('Ignoring event "%s"', event)
                continue

            event['node_uuid'] = node_uuid
            event['state'] = state
            logger.info('Got new event: "%s"', event)
            queue.put(event)

    def _vm_status_thread_check(self):
        """Check if both vm_status threads are alive. Run periodically."""
        if not self._stopping:
            if self.vm_status_monitor_thread and not self.vm_status_monitor_thread.is_alive():
                err = 'VM status monitoring thread is not running - terminating %s!' % self.label
                logger.critical(err)
                raise SystemExit(err)

            if self.vm_status_dispatcher_thread and not self.vm_status_dispatcher_thread.is_alive():
                err = 'VM status dispatcher thread is not running - terminating %s!' % self.label
                logger.critical(err)
                raise SystemExit(err)

    def _set_node_uuid(self):
        """Fetch compute node's UUID"""
        from que.utils import fetch_node_uuid  # Circular imports
        from que.exceptions import NodeError

        try:
            self.node_uuid = fetch_node_uuid()
        except NodeError as exc:
            err = str(exc)
            logger.critical(err)
            raise SystemExit(err)

    def start(self, parent):
        self._set_node_uuid()
        super(FastDaemon, self).start(parent)
        self.vm_status_queue = Queue()
        self.vm_status_watcher = Popen(self.SYSEVENT, bufsize=0, close_fds=True, stdout=PIPE, stderr=STDOUT,
                                       preexec_fn=os.setsid)
        self.vm_status_monitor_thread = Thread(target=self._vm_status_monitor, name='VMStatusMonitor',
                                               args=(self.vm_status_watcher.stdout,))
        self.vm_status_monitor_thread.daemon = True
        self.vm_status_monitor_thread.start()
        self.vm_status_dispatcher_thread = Thread(target=self._vm_status_dispatcher, name='VMStatusDispatcher')
        self.vm_status_dispatcher_thread.daemon = True
        self.vm_status_dispatcher_thread.start()

    def stop(self, parent):
        super(FastDaemon, self).stop(parent)

        if self.vm_status_watcher:
            try:
                self.vm_status_watcher.terminate()
            except NoSuchProcess:
                pass
            else:
                self.vm_status_watcher.wait()


class MgmtDaemon(_PeriodicTaskDaemon):
    """
    Danube Cloud internal mgmt daemon - periodically monitors compute nodes.
    """
    label = 'MgmtDaemon'
    requires = ('celery.worker.consumer:Events', 'celery.worker.consumer:Gossip')

    def __init__(self, parent, **kwargs):
        conf = parent.app.conf
        self.enabled = conf.ERIGONES_MGMT_DAEMON_ENABLED and parent.hostname.startswith(Q_MGMT + '@')
        super(MgmtDaemon, self).__init__(parent, **kwargs)

        if self.enabled:
            self.app = parent.app

            from api.node.status.tasks import node_status_all
            self._periodic_tasks.append(node_status_all)

    def _node_lost(self, worker):
        logger.warn('missed heartbeat from %s', worker.hostname)
        self.dispatcher.send('worker-lost', worker_hostname=worker.hostname)

    def _enable_worker_lost_event(self, gossip):
        # noinspection PyAttributeOutsideInit
        self.dispatcher = gossip.dispatcher
        logger.info('Monkey patching gossip.on_node_lost')
        gossip.on_node_lost = self._node_lost

    def __worker_status_monitor(self):
        from api.node.status.tasks import node_worker_status_change

        def _worker_state(hostname, status, event):
            logger.info('Received %s node worker status: %s', hostname, status)
            queue, node_hostname = hostname.split('@')

            if queue != Q_MGMT:
                node_worker_status_change(node_hostname, queue, status, event)

        def worker_online(event):
            _worker_state(event['hostname'], 'online', event)

        def worker_offline(event):
            _worker_state(event['hostname'], 'offline', event)

        def worker_lost(event):
            _worker_state(event['worker_hostname'], 'offline', event)

        # Here we go
        with self.app.connection() as conn:
            recv = self.app.events.Receiver(conn, handlers={
                'worker-online': worker_online,
                'worker-offline': worker_offline,
                'worker-lost': worker_lost,
            })
            recv.capture(limit=None, timeout=None, wakeup=False)

    def _worker_status_monitor(self):
        """THREAD: Runs celery's task queue receiver and monitors worker related events"""
        while True:
            logger.info('Starting worker status monitor')

            try:
                self.__worker_status_monitor()
            except Exception as exc:
                logger.exception(exc)
                logger.critical('Worker status monitor terminated. Restarting in 5 seconds...')
                sleep(5)

    def start(self, parent):
        self._enable_worker_lost_event(parent.gossip)
        super(MgmtDaemon, self).start(parent)
        worker_status_monitor_thread = Thread(target=self._worker_status_monitor, name='WorkerStatusMonitor')
        worker_status_monitor_thread.daemon = True
        worker_status_monitor_thread.start()
