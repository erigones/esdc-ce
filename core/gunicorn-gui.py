import os

from core.settings import PROJECT_DIR
from core.utils import setup_server_software
setup_server_software()

proc_name = 'gunicorn-gui'
umask = 0o022
django_settings = 'core.settings'
bind = '127.0.0.1:8001'
workers = 2
worker_class = 'sync'
worker_connections = 1000
debug = False
daemon = False
loglevel = 'info'
accesslog = os.path.join(PROJECT_DIR, 'var', 'log', 'gunicorn-gui.access_log')
errorlog = os.path.join(PROJECT_DIR, 'var', 'log', 'gunicorn-gui.error_log')
access_log_format = '"%(h)s %({X-FORWARDED-FOR}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
x_forwarded_for_header = 'X-FORWARDED-FOR'
forwarded_allow_ips = '127.0.0.1'
graceful_timeout = 10
