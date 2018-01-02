from socketio.namespace import BaseNamespace
from logging import getLogger, DEBUG, INFO, ERROR, WARNING
from django.core.cache import cache
from blinker import signal
from gevent import sleep
from collections import deque
# noinspection PyProtectedMember
from django.db import close_old_connections
from django.utils.six import iteritems

from que import TT_MGMT, TT_INTERNAL, TG_DC_UNBOUND
from que.utils import task_prefix_from_task_id, task_id_from_request, get_callback, is_callback, is_logtask
from que.tasks import cq
from api.utils.views import call_api_view
from gui.accounts.utils import get_client_ip

import api.task.views
import api.vm.views
import api.mon.views
import api.node.views

logger = getLogger(__name__)

ACTIVE_USERS = {}
ACTIVE_USERS_LOGMSG0 = 'Active users: %s'
ACTIVE_USERS_LOGMSG1 = ACTIVE_USERS_LOGMSG0 + '\n---- ---- ----\n%s\n---- ---- ----'


def log_active_users():
    count = len(ACTIVE_USERS)
    if count:
        logger.info(ACTIVE_USERS_LOGMSG1, count, '\n'.join('%s:\t%s' % kv for kv in iteritems(ACTIVE_USERS)))
    else:
        logger.info(ACTIVE_USERS_LOGMSG0, count)


class APINamespace(BaseNamespace):
    """
    Socket.IO namespace. It is responsible for socketio interaction between user browser and the API.
    After connecting to this namespace a que event monitor is started and waits for task signals.
    """
    def process_packet(self, packet):
        """
        Bug #chili-292 - Crafted websocket "packet" hangs socket.io thread.
        """
        try:
            return super(APINamespace, self).process_packet(packet)
        except KeyError as e:
            logger.info('Caught exception in process_packet(%s', packet)
            logger.exception(e)
            return

    def exception_handler_decorator(self, fun):
        """Close DB connection here - https://github.com/abourget/gevent-socketio/issues/174"""
        def wrap(*args, **kwargs):
            self.log('APINamespace.%s(%s, %s)', fun.__name__, args, kwargs, level=DEBUG)
            try:
                return fun(*args, **kwargs)
            finally:
                close_old_connections()
        return wrap

    # noinspection PyAttributeOutsideInit
    def setup_user(self):
        self.dc = self.request.dc = self.request.user.current_dc
        self.dc_id = str(self.dc.id)
        self.username = self.request.user.username
        self.log('Set dc_id to %s (%s) for user %s (%s)', self.dc_id, self.dc, self.user_id, self.username)

    # noinspection PyAttributeOutsideInit
    def initialize(self):
        request = self.request
        self.user_id = str(request.user.id)
        self.user_ip = get_client_ip(request)
        self.sess_id = self.socket.sessid
        self.session_key = request.session.session_key
        self.last_tasks = deque(maxlen=100)
        self.setup_user()
        self.log('API socketio session started for user %s (%s) from %s', self.user_id, self.username, self.user_ip)

    def log(self, msg, *args, **kwargs):
        if args:
            # noinspection PyAugmentAssignment
            msg = msg % args
        level = kwargs.get('level', INFO)
        logger.log(level, '[%s - %s - %s] %s', self.username, self.session_key, self.sess_id, msg)

    def disconnect(self, *args, **kwargs):
        self.log('Unsubscribing from que event monitor')
        self.kill_local_jobs()
        super(APINamespace, self).disconnect(*args, **kwargs)

    def subscribe(self):
        self.spawn(self.que_monitor)
        self.log('Watching que event monitor')
        self.emit('subscribed', self.sess_id)

    # noinspection PyUnusedLocal
    def on_unsubscribe(self, *args):
        self.disconnect()

    # noinspection PyUnusedLocal
    def on_subscribe(self, *args):
        self.log('Subscribing to que event monitor')
        if self.request.user.is_authenticated():
            self.subscribe()

    def get_request(self, method):
        request = self.request
        request.method = method
        return request

    def _api_task_status(self, task_id):
        return call_api_view(self.get_request('GET'), None, api.task.views.task_status, task_id=task_id)

    def _call_api_view(self, method, viewspace, view, args, kwargs):
        kwargs = dict(kwargs)
        args = list(args)

        self.log('Calling %s on API view "%s.%s" with args: "%s" and kwargs: "%s"',
                 method, viewspace.__name__, view, args, kwargs)

        if method not in ('GET', 'POST', 'PUT', 'DELETE'):
            self.log('Method "%s" not allowed', method, level=ERROR)
            self.emit('error', 'Method not allowed')
            return

        request = self.get_request(method)

        # Every api view called from here expects a data keyword parameter, which should not be None if called from sio
        if 'data' not in kwargs or not kwargs['data']:
            kwargs['data'] = {}

        try:
            if view.startswith('_'):
                raise AttributeError
            f = getattr(viewspace, view)
        except AttributeError:
            self.log('API view "%s.%s not found', viewspace.__name__, view, level=ERROR)
            self.emit('error', 'API view "%s.%s" not found' % (viewspace.__name__, view))
            return

        try:
            r = call_api_view(request, None, f, *args, **kwargs)
        except Exception as e:  # Catch all, because this would break the user socket.io instance
            self.log('API view %s "%s.%s" failed', method, viewspace.__name__, view, level=ERROR)
            logger.exception(e)
            return

        if r.status_code in (200, 201):
            self.log('API view %s "%s.%s (%s, %s)" has finished (%s) with output "%s"',
                     method, viewspace.__name__, view, args, kwargs, r.status_code, r.data)

            if isinstance(r.data, dict) and 'task_id' in r.data:
                task_id = r.data['task_id']

                if task_id in self.last_tasks:
                    self.log('Ignoring new task %s, because we already know (1)', task_id)
                    return

                self.last_tasks.append(task_id)

        else:  # API call failed because of some validation error
            self.log('API view %s "%s.%s (%s, %s)" has finished (%s) with output "%s"',
                     method, viewspace.__name__, view, args, kwargs, r.status_code, r.data, level=WARNING)

        self.emit('message', view, method, r.status_code, r.data, args, kwargs,
                  getattr(r, 'apiview', {}), getattr(r, 'apidata', {}))

    def on_task(self, method, view, args, kwargs):
        # noinspection PyTypeChecker
        self._call_api_view(method, api.task.views, view, args, kwargs)

    def on_vm(self, method, view, args, kwargs):
        # noinspection PyTypeChecker
        self._call_api_view(method, api.vm.views, view, args, kwargs)

    def on_mon(self, method, view, args, kwargs):
        # noinspection PyTypeChecker
        self._call_api_view(method, api.mon.views, view, args, kwargs)

    def on_node(self, method, view, args, kwargs):
        # noinspection PyTypeChecker
        self._call_api_view(method, api.node.views, view, args, kwargs)

    def on_user_vms_tags(self, user_vms_tags):
        self.request.user.vms_tags = user_vms_tags

    def on_dc_switch(self):
        # Reload user object in request
        self.request.user = self.request.user.__class__.objects.get(pk=self.request.user.pk)
        self.setup_user()
        self.set_active_user()

        # Inform other sessions for this user about the DC change
        task_id = task_id_from_request(self.user_id, tt=TT_INTERNAL, tg=TG_DC_UNBOUND, dc_id=self.dc_id)
        self.last_tasks.append(task_id)
        new_task = signal('task-for-' + self.user_id)
        new_task.send('_dc_switch', task_id=task_id, event_status='internal')

    # noinspection PyUnusedLocal
    def _dc_switch(self, task_id, **kwargs):
        self.emit('info', 'dc_switch')

    def _task_internal(self, task_id, sender, **kwargs):
        if task_id in self.last_tasks:
            self.log('Ignoring internal task %s (%s), because we already know (3)', task_id, sender, level=DEBUG)
            return

        try:
            fun = getattr(self, sender)
        except AttributeError:
            self.log('Internal method "%s not found', sender, level=ERROR)
        else:
            self.log('Running internal method %s(%s, %s) ', sender, task_id, kwargs)
            fun(task_id, **kwargs)

    def _task_sent(self, task_id, event_status, event, tt):
        if task_id in self.last_tasks:
            self.log('Ignoring new task %s, because we already know (2)', task_id, level=DEBUG)
            return
        elif tt == TT_MGMT:
            self.log('Ignoring mgmt task %s, because we never called it', task_id, level=DEBUG)
            return

        self.last_tasks.append(task_id)
        r = self._api_task_status(task_id)
        self.log('Task %s %s', task_id, event_status)
        self.emit('message', event['view'], event['method'], r.status_code, r.data, event['args'], event['kwargs'],
                  event['apiview'], event['apidata'])

    def _task_status(self, task_id, event_status, tt):
        if tt == TT_MGMT and task_id not in self.last_tasks:
            self.log('Ignoring mgmt task %s, because we never called it', task_id, level=DEBUG)
            return

        task = cq.AsyncResult(task_id)

        if get_callback(task):
            self.log('Ignoring task %s, because it has a callback', task_id, level=DEBUG)
            return

        parent_task_id = is_callback(task)

        if parent_task_id:
            _task_id = task_id
            task_id = parent_task_id
            self.log('Changing task %s to %s, because it is a callback', _task_id, task_id, level=DEBUG)
        elif is_logtask(task):
            self.log('Ignoring task %s, because it is a logtask without caller', task_id)
            return

        # Try to get the apiview information from cache
        apiview = None
        # noinspection PyBroadException
        try:
            apiview = cache.get('sio-' + task_id)
        except Exception:
            pass
        if not apiview:
            apiview = {}

        res = self._api_task_status(task_id)
        self.log('Task %s %s', task_id, event_status)
        self.emit('task_status', res.data, apiview)

    def _task_event(self, task_id, event_result):
        # Rename node_hostname or vm_hostname to hostname (because worker hostname is not needed)
        if 'node_hostname' in event_result:
            event_result['hostname'] = event_result['node_hostname']
        elif 'vm_hostname' in event_result:
            event_result['hostname'] = event_result['vm_hostname']

        self.log('Task %s %s', task_id, event_result.get('_event_', '???'))
        self.emit('task_event', event_result)

    def set_active_user(self):
        ACTIVE_USERS[self.sess_id] = (self.user_id, self.username, self.dc.name, self.session_key, self.user_ip)
        log_active_users()

    def del_active_user(self):
        del ACTIVE_USERS[self.sess_id]
        log_active_users()

    def que_monitor(self):
        new_task = signal('task-for-' + self.user_id)

        # noinspection PyUnusedLocal
        @new_task.connect
        def process_task(sender, task_id=None, event_status=None, **kwargs):
            self.log('Got signal for %s task %s', event_status, task_id, level=DEBUG)
            task_prefix = task_prefix_from_task_id(task_id)

            if task_prefix[4] != self.dc_id and task_prefix[3] != TG_DC_UNBOUND:
                self.log('Ignoring dc-bound task %s, because user works in DC %s', task_id, self.dc_id)
                return

            if event_status == 'sent':
                self._task_sent(task_id, event_status, sender, task_prefix[1])
            elif event_status == 'event':
                self._task_event(task_id, sender)
            elif event_status == 'internal':
                self._task_internal(task_id, sender, **kwargs)
            else:
                self._task_status(task_id, event_status, task_prefix[1])

        self.log('Ready')
        self.set_active_user()

        try:
            while True:
                sleep(1.0)
        finally:
            self.log('Game over')
            self.del_active_user()
