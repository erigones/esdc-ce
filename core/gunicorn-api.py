import os

from core.settings import PROJECT_DIR
from core.utils import setup_server_software
setup_server_software()
# gevent worker class does the monkey patching

proc_name = 'gunicorn-api'
umask = 0o022
django_settings = 'core.settings'
bind = '127.0.0.1:8002'
workers = 1
worker_class = 'gevent'
worker_connections = 500
debug = False
daemon = False
loglevel = 'info'
accesslog = os.path.join(PROJECT_DIR, 'var', 'log', 'gunicorn-api.access_log')
errorlog = os.path.join(PROJECT_DIR, 'var', 'log', 'gunicorn-api.error_log')
access_log_format = '"%(h)s %({X-FORWARDED-FOR}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
x_forwarded_for_header = 'X-FORWARDED-FOR'
forwarded_allow_ips = '127.0.0.1'
timeout = 60
graceful_timeout = 10


# noinspection PyUnusedLocal
def post_fork(server, worker):
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()
    worker.log.info('Made psycopg2 green :)')
