import os

from core.settings import PROJECT_DIR
from core.utils import setup_server_software
from socketio.sgunicorn import GeventSocketIOWorker
from socketio.server import SocketIOServer
from gevent import monkey, spawn

monkey.patch_all()
setup_server_software()

proc_name = 'gunicorn-sio'
umask = 0o022
django_settings = 'core.settings'
bind = '127.0.0.1:8000'
workers = 1  # NEVER set to more than 1 when using GeventSocketIOWorker
worker_class = 'core.gunicorn-sio.ESDCGeventSocketIOWorker'
worker_connections = 500
debug = False
daemon = False
loglevel = 'info'
accesslog = os.path.join(PROJECT_DIR, 'var', 'log', 'gunicorn-sio.access_log')
errorlog = os.path.join(PROJECT_DIR, 'var', 'log', 'gunicorn-sio.error_log')
access_log_format = '"%(h)s %({X-FORWARDED-FOR}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
x_forwarded_for_header = 'X-FORWARDED-FOR'
forwarded_allow_ips = '127.0.0.1'
graceful_timeout = 10


# noinspection PyAbstractClass
class ESDCSocketIOServer(SocketIOServer):
    def __init__(self, *args, **kwargs):
        kwargs['transports'] = ['websocket', 'xhr-polling']
        super(ESDCSocketIOServer, self).__init__(*args, **kwargs)


# noinspection PyAbstractClass
class ESDCGeventSocketIOWorker(GeventSocketIOWorker):
    server_class = ESDCSocketIOServer
    policy_server = False


def post_fork(server, worker):
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()
    worker.log.info('Made psycopg2 green :)')
    from sio.monitor import que_monitor_loop
    spawn(que_monitor_loop, server, worker)
