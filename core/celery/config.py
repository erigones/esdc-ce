CELERY_SEND_TASK_ERROR_EMAILS = False
SERVER_EMAIL = 'danubecloud@example.com'
ADMINS = ()
BROKER_URL = 'amqp://esdc:S3cr3tP4ssw0rd@127.0.0.1:5672/esdc'
BROKER_POOL_LIMIT = 1000
BROKER_CONNECTION_MAX_RETRIES = 0  # forever
BROKER_HEARTBEAT = 10
CELERY_RESULT_BACKEND = 'redis://:S3cr3tP4ssw0rd@127.0.0.1:6379/0'
CELERY_TASK_RESULT_EXPIRES = 3600  # can be lower
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Etc/UTC'
CELERY_ENABLE_UTC = True
CELERY_IMPORTS = ('que.tasks', )
# CELERY_ROUTES = {}
CELERY_DISABLE_RATE_LIMITS = True
CELERY_DEFAULT_QUEUE = 'default'
CELERY_DEFAULT_EXCHANGE_TYPE = 'direct'
CELERY_DEFAULT_ROUTING_KEY = 'default'
CELERY_ACKS_LATE = False
CELERY_TRACK_STARTED = True
CELERY_SEND_TASK_SENT_EVENT = False
CELERY_ACCEPT_CONTENT = ('pickle', 'json')
CELERYD_CONCURRENCY = 1
CELERYD_PREFETCH_MULTIPLIER = 1

ERIGONES_DEFAULT_DC = 1
ERIGONES_TASK_DEFAULT_EXPIRES = 300
ERIGONES_LOGTASK = 'api.task.tasks.task_log_cb'
ERIGONES_TASK_USER = '7'
ERIGONES_TASK_USERNAME = '_system'
ERIGONES_CACHE_PREFIX = 'esdc:'
ERIGONES_MGMT_STARTUP_TASK = 'api.system.tasks.mgmt_worker_startup'
ERIGONES_NODE_SYSINFO_TASK = 'api.node.sysinfo.tasks.node_sysinfo_cb'
ERIGONES_NODE_STATUS_CHECK_TASK = 'api.node.status.tasks.node_worker_status_check_all'
ERIGONES_VM_STATUS_TASK = 'api.vm.status.tasks.vm_status_event_cb'
ERIGONES_MGMT_WORKERS = ('mgmt@mgmt01.local',)
ERIGONES_MGMT_DAEMON_ENABLED = True
ERIGONES_FAST_DAEMON_ENABLED = True
ERIGONES_PING_TIMEOUT = 0.4
ERIGONES_CHECK_USER_TASK_TIMEOUT = 30
ERIGONES_DEFAULT_RETRY_DELAY = 60
ERIGONES_MAX_RETRIES = None
ERIGONES_TASK_MGMT_CB_DEFAULT_RETRY_DELAY = 30
ERIGONES_TASK_MGMT_CB_MAX_RETRIES = None
ERIGONES_UPDATE_SCRIPT = 'bin/esdc-git-update'

CELERYBEAT_MAX_LOOP_INTERVAL = 30
CELERYBEAT_SCHEDULER = 'que.beat.ESDCDatabaseScheduler'
CELERYBEAT_SCHEDULE = {}

# Allow any settings to be defined in local_settings.py which is ignored in our
# version control system allowing for settings to be defined (overwritten) per
# machine, and also for security reasons not to store passwords in version
# control.
try:
    from local_config import *
except ImportError:
    pass
