# -*- coding: utf-8 -*-
# Django settings for ESDC.

from os import path
from core.external.utils import collect_third_party_apps_and_settings

PROJECT_DIR = path.abspath(path.join(path.dirname(__file__), '..'))

DEBUG = False
TEMPLATE_DEBUG = DEBUG
JAVASCRIPT_DEBUG = DEBUG
SQL_DEBUG = False
ANALYTICS = False  # Analytics code instead of True

ADMINS = (
    ('DanubeCloud', 'support@example.com'),
)

MANAGERS = ADMINS

# Default test DB
DATABASES = {
    'esdc': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'esdc',
        'USER': 'esdc',
        'PASSWORD': 'S3cr3tP4ssw0rd',
        'HOST': '127.0.0.1',
        'PORT': '6432',
    },
    'pdns': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'pdns',
        'USER': 'esdc',
        'PASSWORD': 'S3cr3tP4ssw0rd',
        'HOST': '127.0.0.1',
        'PORT': '6432',
    },
}
DATABASES['default'] = DATABASES['esdc']
# NOTE: Do not enable atomic views. Use the django transaction management manually.
#       Some view must not be atomic, e.g. because of signals.

# DB router: pdns app goes into pdns DB, everything else goes into esdc DB
DATABASE_ROUTERS = ('core.db.AppRouter',)

# Caching
CACHE_KEY_PREFIX = 'core'
CACHES = {
    'redis': {
        'BACKEND': 'redis_cache.RedisCache',
        'LOCATION': '127.0.0.1:6379',
        'TIMEOUT': None,
        'OPTIONS': {
            'DB': 0,
            'PASSWORD': 'S3cr3tP4ssw0rd',
            'PARSER_CLASS': 'redis.connection.HiredisParser'
        },
        'KEY_PREFIX': CACHE_KEY_PREFIX,
    }
}
CACHES['default'] = CACHES['redis']

# Session engine
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# Local time zone for this installation.
TIME_ZONE = 'Etc/UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
# Default language that is loaded if translation is not found.
LANGUAGE_CODE = 'en-us'

# Languages we provide translations for.
LANGUAGES = (
    ('en', 'English'),
    ('it', 'Italiano'),
    #  ('sk', 'Slovensky (beta)'),
)

# Cookies we create will have names with es_ prefix
CSRF_COOKIE_NAME = 'es_csrftoken'
SESSION_COOKIE_NAME = 'es_sessionid'
LANGUAGE_COOKIE_NAME = 'es_language'
TIMEZONE_SESSION_KEY = 'django_timezone'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
MEDIA_ROOT = path.join(PROJECT_DIR, 'var', 'lib')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Example: "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
STATIC_ROOT = path.join(PROJECT_DIR, 'var', 'www', 'static')

# URL prefix for static files.
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = '-&amp;yqav1*(fqt+#qzq%)!92(ao3qonhn!8n5y9=xy$g8%2w_#=z'

# List of callables that know how to import templates from various sources.
# TEMPLATE_LOADERS = (
#     'django.template.loaders.filesystem.Loader',
#     'django.template.loaders.app_directories.Loader',
# )

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',

    'gui.middleware.ExceptionMiddleware',
    'gui.middleware.AjaxMiddleware',
    'gui.middleware.TimezoneMiddleware',
    'gui.middleware.ImpersonateMiddleware',
    'gui.middleware.DebugMiddleware',
    'vms.middleware.DcMiddleware',
    'api.middleware.APISyncMiddleware',
)

ROOT_URLCONF = 'core.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'core.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': (
            # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
            # Always use forward slashes, even on Windows.
            # Don't forget to use absolute paths, not relative paths.
            path.join(PROJECT_DIR, 'core', 'templates'),
        ),
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.i18n',
                'django.template.context_processors.request',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.contrib.messages.context_processors.messages',
                'gui.context_processors.common_stuff',
            ]
        },
    },
]

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'gunicorn',
    'taggit',
    'django_celery_beat',
    'gui.apps.GuiConfig',
    'vms.apps.VmsConfig',
    'api.apps.ApiConfig',
    'api.sms.apps.SmsConfig',
    'api.authtoken.apps.AuthTokenConfig',
    'pdns.apps.PdnsConfig',
    'sio.apps.SioConfig',
    'core.apps.CoreConfig',
    'compressor',
)

MODULES = [
    'ACL_ENABLED',
    'API_ENABLED',
    'MON_ZABBIX_ENABLED',
    'DNS_ENABLED',
    'REGISTRATION_ENABLED',
    'SUPPORT_ENABLED',
    'VMS_DC_ENABLED',
    'VMS_VM_SNAPSHOT_ENABLED',
    'VMS_VM_BACKUP_ENABLED',
    'VMS_ZONE_ENABLED',
    'SMS_ENABLED',
]

# Enable/Disable 3rd party apps (to be done in your local_settings.py)
THIRD_PARTY_APPS_ENABLED = True

LOCALE_PATHS = (path.join(PROJECT_DIR, 'core'),)
FORMAT_MODULE_PATH = 'core.formats'
AUTH_USER_MODEL = 'gui.User'
SESSION_COOKIE_AGE = 86400
USE_X_FORWARDED_HOST = True
# During management appliance building phase we do not
# know which hosts should be allowed. Therefore, we
# allow everything.
ALLOWED_HOSTS = ('*',)
INTERNAL_IPS = ('127.0.0.1', '::1')
SERVER_EMAIL = 'default@example.com'
DEFAULT_FROM_EMAIL = 'noreply@example.com'
EMAIL_ENABLED = True
EMAIL_BACKEND = 'api.email.SMTPEmailBackend'
EMAIL_HOST = '127.0.0.1'
EMAIL_PORT = 25
EMAIL_HOST_PASSWORD = ''
EMAIL_HOST_USER = ''
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 30
EMAIL_SUBJECT_PREFIX = '[Danube Cloud] '
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/servers/'
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
PASSWORD_RESET_TIMEOUT_DAYS = 3
GEOIP_PATH = '/usr/share/GeoIP'
GEOIP_LIBRARY_PATH = '/usr/lib64/libGeoIP.so.1'
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

ADMIN_URL = 'admin/'  # Without leading slash!

EMAIL_ADMINS = False

TMPDIR = path.join(PROJECT_DIR, 'var', 'tmp')
LIBDIR = path.join(PROJECT_DIR, 'var', 'lib')
LOGDIR = path.join(PROJECT_DIR, 'var', 'log')
RUNDIR = path.join(PROJECT_DIR, 'var', 'run')

# Location of key/cert files needed to authenticate against update server
UPDATE_KEY_FILE = path.join(LIBDIR, 'update.key')
UPDATE_CERT_FILE = path.join(LIBDIR, 'update.crt')

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        },
        'require_email_admins': {
            '()': 'core.utils.RequireEmailAdmins'
        },
    },

    'formatters': {
        'verbose': {
            'format': '%(asctime)s %(levelname)s [%(name)s] [%(process)d %(thread)d]: %(message)s'
        },
        'simple': {
            'format': '%(asctime)s %(levelname)s [%(name)s]: %(message)s'
        },
    },

    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false', 'require_email_admins'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'messages': {
            'level': 'DEBUG',
            'class': 'logging.handlers.WatchedFileHandler',
            'formatter': 'simple',
            'filename': path.join(LOGDIR, 'main.log'),
        },
        'authlog': {
            'level': 'DEBUG',
            'class': 'logging.handlers.WatchedFileHandler',
            'formatter': 'simple',
            'filename': path.join(LOGDIR, 'auth.log'),
        },
        'tasklog': {
            'level': 'DEBUG',
            'class': 'logging.handlers.WatchedFileHandler',
            'formatter': 'simple',
            'filename': path.join(LOGDIR, 'task.log'),
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },

    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django': {
            'handlers': ['messages'],
            'propagate': True,
            'level': 'INFO',
        },
        'core': {
            'handlers': ['messages'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'api': {
            'handlers': ['messages'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'que': {
            'handlers': ['tasklog'],
            'propagate': True,
            'level': 'INFO',
        },
        'gui.auth': {
            'handlers': ['authlog'],
            'propagate': False,
            'level': 'DEBUG',
        },
        'api.auth': {
            'handlers': ['authlog'],
            'propagate': False,
            'level': 'DEBUG',
        },
        'gui': {
            'handlers': ['messages'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'pdns': {
            'handlers': ['messages'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'vms': {
            'handlers': ['messages'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'sio': {
            'handlers': ['messages'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'eslic': {
            'handlers': ['messages'],
            'propagate': True,
            'level': 'DEBUG',
        },
    }
}

COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_OUTPUT_DIR = 'cache'
COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.CSSMinFilter',
]
COMPRESS_JS_FILTERS = [
    'compressor.filters.jsmin.JSMinFilter',
]
COMPRESS_OFFLINE_CONTEXT = {
    'STATIC_URL': STATIC_URL,
    'load_base': 'base.html',
}
COMPRESS_DEBUG_TOGGLE = False

###
# Settings for custom cloud (Danube Cloud)
######
ADMIN_USER = 1
ADMIN_USERNAME = 'admin'
SYSTEM_USER = 7
SYSTEM_USERNAME = '_system'

API_SYNC_TIMEOUT = 3600
API_LOCK_TIMEOUT = 300

SHADOW_EMAIL = ''  # bcc for every outgoing email

TASK_LOG_BASENAME = 'api.task.log'
TASK_LOG_LASTSIZE = 10
TASK_LOG_STAFF_ID = 0

AUTHTOKEN_DURATION = 3600  # Seconds

SOCKETIO_URL = '/'
SOCKETIO_HTTP_ORIGIN = '*'

GUACAMOLE_KEY = 'esdc:guacamole:'
GUACAMOLE_URI = 'http://127.0.0.1:8080/guacamole'
GUACAMOLE_WSS = '/guacamole/websocket-tunnel'
GUACAMOLE_HTU = '/guacamole/tunnel'
GUACAMOLE_TOKEN = 'guacamole-auth-token'
GUACAMOLE_COOKIE = 'JSESSIONID'
GUACAMOLE_COOKIEPATH = '/guacamole'
GUACAMOLE_COOKIEDOMAIN = None
GUACAMOLE_USERAGENT = 'esdc/2.3'
GUACAMOLE_TIMEOUT = 5
GUACAMOLE_DEFAULT_ZOOM = False

DNS_ENABLED = True  # Module
DNS_MGMT_DOMAIN = 'local'  # Internal setting related to initial_data
DNS_HOSTMASTER = 'hostmaster@example.com'  # This will be used as a placeholder for generating SOA records
DNS_NAMESERVERS = ['ns1.' + DNS_MGMT_DOMAIN]  # Items will be used as a placeholder for generating SOA and NS records
DNS_SOA_DEFAULT = '{nameserver} {hostmaster} 2013010100 28800 7200 604800 86400'  # For auto-generated SOA records
DNS_PTR_DEFAULT = '{hostname}'  # Content of VM's PTR record
DNS_DOMAIN_TYPE_DEFAULT = 'MASTER'

ESLIC_ENABLED = False  # Module. Enterprise Edition.

# List of available currencies, user can set in his profile. Not used ESDC CE, available support for 3rd party apps.
CURRENCY = (
    ('EUR', '€'),
    # ('USD', '$'),
)
CURRENCY_DEFAULT = 'EUR'

REGISTRATION_ENABLED = False  # Module. Enable SMS_ENABLED if True
COMPANY_NAME = 'Danube Cloud'
TOS_LINK = ''
SITE_LINK = 'http://127.0.0.1:8000'
SITE_NAME = 'Danube Cloud'
SITE_SIGNATURE = SITE_NAME + '\r\n' + SITE_LINK
SITE_LOGO = ''
SITE_ICON = ''

PROFILE_SSH_KEY_LIMIT = 10
PROFILE_COUNTRY_CODE_DEFAULT = 'SK'
PROFILE_PHONE_PREFIX_DEFAULT = '+421'
PROFILE_TIME_ZONE_DEFAULT = 'Europe/Bratislava'
PROFILE_PHONE_REQUIRED = False
PROFILE_ADDRESS_REQUIRED = False
PROFILE_NEWSLETTER_ENABLED = False
PROFILE_USERTYPE_DEFAULT = 1  # Personal account

SMS_REGISTRATION_ENABLED = False
SMS_ENABLED = False  # Module. Required if SMS_REGISTRATION_ENABLED=True
SMS_PREFERRED_SERVICE = 'smsapi'  # Former HQSMS
SMS_FROM_NUMBER = 'DanubeCloud'
SMS_SERVICE_USERNAME = ''
SMS_SERVICE_PASSWORD = ''
SMS_EXPIRATION_HOURS = 1  # In how many hours does SMS expire?

MON_ZABBIX_ENABLED = False  # Module
_MON_ZABBIX_VM_SYNC = True  # local, internal, hidden
MON_ZABBIX_VM_SYNC = True  # local, external
MON_ZABBIX_NODE_SYNC = True  # global, internal
MON_ZABBIX_VM_SLA = True  # local, internal
MON_ZABBIX_NODE_SLA = True  # global, internal

MON_ZABBIX_SENDER = '/usr/bin/zabbix_sender'  # hidden
MON_ZABBIX_SERVER = 'https://example.com/zabbix'  # local, internal+external
MON_ZABBIX_SERVER_EXTERNAL_URL = ''
MON_ZABBIX_SERVER_SSL_VERIFY = True  # local, internal+external
MON_ZABBIX_TIMEOUT = 15  # local, internal+external
MON_ZABBIX_USERNAME = 'Admin'  # local, internal+external
MON_ZABBIX_PASSWORD = 'zabbix'  # local, internal+external
MON_ZABBIX_HTTP_USERNAME = ''  # local, internal+external
MON_ZABBIX_HTTP_PASSWORD = ''  # local, internal+external

MON_ZABBIX_HOSTGROUP_NODE = 'Compute nodes'  # global, internal
MON_ZABBIX_HOSTGROUPS_NODE = ('Notifications',)  # global, internal
_MON_ZABBIX_TEMPLATES_NODE = ('t_role-compute', 't_custom_alerts')  # global, internal, hidden
MON_ZABBIX_TEMPLATES_NODE = ()  # global, internal
_MON_ZABBIX_ITS_PARENT_NODE = 'Compute Nodes'  # global, internal, hidden
_MON_ZABBIX_ITS_TRIGGERS_NODE = (  # global, internal, hidden
    ('ICMP', 'Server is unreachable (ICMP)'),
    ('Zabbix Agent', 'Zabbix agent on {HOST.NAME} is unreachable for 3 minutes'),
)

_MON_ZABBIX_HOSTGROUP_VM = 'Virtual machines'  # global, internal, hidden
_MON_ZABBIX_HOSTGROUPS_VM = ('Notifications',)  # global, internal, hidden
MON_ZABBIX_HOSTGROUP_VM = _MON_ZABBIX_HOSTGROUP_VM  # local, external
MON_ZABBIX_HOSTGROUPS_VM = ('Notifications',)  # local, external
MON_ZABBIX_HOSTGROUPS_VM_RESTRICT = True  # local, external
MON_ZABBIX_HOSTGROUPS_VM_ALLOWED = ('Notifications',)  # local, external
_MON_ZABBIX_TEMPLATES_VM = (  # global, internal, hidden
    't_vm_disk_space',
    't_custom_alerts',
    't_vm_disk_latency',
    't_vm_zone_vfs',
    't_vm_zone_zfs',
    't_vm_memory',
    't_vm_zone_cpu',
    't_vm_zone_dataset',
)
_MON_ZABBIX_TEMPLATES_VM_NIC = ('t_vm_network_net{net}',)  # global, internal, hidden
_MON_ZABBIX_TEMPLATES_VM_DISK = ('t_vm_kvm_disk{disk_id}_io',)  # global, internal, hidden
MON_ZABBIX_TEMPLATES_VM = ()  # local, external
MON_ZABBIX_TEMPLATES_VM_NIC = ()  # local, external
MON_ZABBIX_TEMPLATES_VM_DISK = ()  # local, external
MON_ZABBIX_TEMPLATES_VM_MAP_TO_TAGS = False  # local, external
MON_ZABBIX_TEMPLATES_VM_RESTRICT = False  # local, external
MON_ZABBIX_TEMPLATES_VM_ALLOWED = ()  # local, external

MON_ZABBIX_HOST_VM_PORT = 10050  # local, external
MON_ZABBIX_HOST_VM_USEIP = True  # local, external
MON_ZABBIX_HOST_VM_PROXY = ''  # local, external

MON_ZABBIX_GRAPH_MAX_HISTORY = 518400  # 6 days; global, internal+external
MON_ZABBIX_GRAPH_MAX_PERIOD = 14400  # 4 hours; global, internal+external

MON_ZABBIX_MEDIA_TYPE_EMAIL = 'E-mail'
MON_ZABBIX_MEDIA_TYPE_PHONE = 'SMS'
MON_ZABBIX_MEDIA_TYPE_JABBER = 'Ludolph'

SUPPORT_ENABLED = True  # Module
SUPPORT_EMAIL = 'support@example.com'
SUPPORT_PHONE = ''
SUPPORT_USER_CONFIRMATION = True
FAQ_ENABLED = False  # Module

VMS_SDC_VERSION = '7.0'

VMS_VM_JSON_DEFAULTS = {
    'internal_metadata': {
        'author': 'Erigones',
        'installed': False,
    },
}

VMS_VM_QEMU_GUEST_AGENT_SOCKET = '/tmp/vm.qga'
VMS_VM_QEMU_EXTRA_OPTS = '-chardev socket,path=/tmp/vm.qga,server,nowait,id=qga0 -device virtio-serial ' \
                         '-device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0'

API_ENABLED = True  # Module
API_LOG_USER_CALLBACK = True  # Whether to log user callbacks into task log

VMS_ZONE_ENABLED = True  # Module
VMS_ZONE_FEATURE_LEVEL = 1

VMS_DC_ENABLED = True  # Module

# Internal VMs
VMS_VM_CFGDB01 = 'ddca4052-effd-47fb-9e70-e6807025d8b4'
VMS_VM_MGMT01 = 'f7860689-c435-4964-9f7d-2d2d70cfe389'
VMS_VM_IMG01 = '2b504f53-1c0b-4ceb-bfda-352f549a70e1'
VMS_VM_MON01 = 'a28faa4d-d0ee-4593-938a-f0d062022b02'
VMS_VM_DNS01 = '6546040c-ca68-4c5b-8a19-a42e487267c9'

VMS_INTERNAL = (VMS_VM_CFGDB01, VMS_VM_MGMT01, VMS_VM_IMG01, VMS_VM_MON01, VMS_VM_DNS01)
VMS_NO_SHUTDOWN = ()

VMS_DC_MAIN = 'main'  # Default DC name
VMS_DC_ADMIN = 'admin'  # Admin DC name
VMS_DC_DEFAULT = 1  # Default DC ID
VMS_NODE_DC_DEFAULT = VMS_DC_DEFAULT  # DC ID - Must be equal to VMS_DC_DEFAULT or None
VMS_NODE_USER_DEFAULT = ADMIN_USER
VMS_NODE_SSH_KEYS_SYNC = True
VMS_NODE_SSH_KEYS_DEFAULT = []
VMS_NET_DEFAULT = 'lan'
VMS_NET_ADMIN = 'admin'
VMS_NET_ADMIN_OVERLAY = 'adminoverlay'
VMS_NET_VLAN_RESTRICT = True
VMS_NET_VXLAN_RESTRICT = True
VMS_NET_VLAN_ALLOWED = []
VMS_NET_VXLAN_ALLOWED = []
VMS_NET_LIMIT = None
VMS_IMAGE_VM = VMS_VM_IMG01
VMS_IMAGE_VM_NIC = 1
VMS_IMAGE_VM_DATASETS_DIR = '/{zfs_filesystem}/root/datasets'  # Image upload directory on ImageVm's compute node
VMS_IMAGE_IMGADM_CONF = {
    'dockerImportSkipUuids': True,
    'upgradedToVer': '3.0.0',
    'sources': [],
}
VMS_IMAGE_SOURCES = []
VMS_IMAGE_LIMIT = None
VMS_IMAGE_REPOSITORIES = {
    'danubecloud': 'https://images.danube.cloud',
    'images.joyent.com': 'https://images.joyent.com',
}
VMS_ISO_DIR = '/iso'
VMS_ISO_RESCUECD = 'rescuecd.iso'
VMS_ISO_LIMIT = None
VMS_TEMPLATE_LIMIT = None
VMS_VM_DEFINE_LIMIT = None
VMS_VM_DOMAIN_DEFAULT = 'lan'
VMS_VM_OSTYPE_DEFAULT = 1
VMS_VM_CPU_TYPE_DEFAULT = 'qemu64'
VMS_VM_BRAND_SUNOS_ZONE_DEFAULT = 'joyent'
VMS_VM_BRAND_LX_ZONE_DEFAULT = 'lx'
VMS_VM_LX_KERNEL_VERSION_DEFAULT = '4.4'
VMS_VM_MONITORED_DEFAULT = True
VMS_VM_CPU_SHARES_DEFAULT = 100
VMS_VM_CPU_BURST_RATIO = 1.0    # Do _NOT_ change this, unless you know what you are doing!
VMS_VM_CPU_BURST_DEFAULT = 100  # Do _NOT_ change this, unless you know what you are doing!
VMS_VM_CPU_CAP_REQUIRED = True  # Whether the cpu_cap and vcpus count can be zero for SunOS and LX zones
VMS_VM_KVM_MEMORY_OVERHEAD = 256  # MB
VMS_VM_SWAP_MULTIPLIER = 2  # Cannot be lower than 1
VMS_VM_ZFS_IO_PRIORITY_DEFAULT = 100
VMS_VM_RESOLVERS_DEFAULT = ['8.8.4.4', '8.8.8.8']
VMS_VM_SSH_KEYS_DEFAULT = []
VMS_VM_MDATA_DEFAULT = {}
VMS_VM_STOP_TIMEOUT_DEFAULT = 180
VMS_VM_STOP_WIN_TIMEOUT_DEFAULT = 300
VMS_DISK_MODEL_DEFAULT = 'virtio'
VMS_DISK_COMPRESSION_DEFAULT = 'lz4'
VMS_DISK_IMAGE_DEFAULT = ''
VMS_DISK_IMAGE_ZONE_DEFAULT = 'base-64-es'  # TODO: Rename to VMS_DISK_IMAGE_SUNOS_ZONE_DEFAULT
VMS_DISK_IMAGE_LX_ZONE_DEFAULT = 'alpine-3'
VMS_NIC_MODEL_DEFAULT = 'virtio'
VMS_NIC_MONITORING_DEFAULT = 1
VMS_VGA_MODEL_DEFAULT = 'std'
VMS_STORAGE_DEFAULT = 'zones'
VMS_VM_ZONE_USER_SCRIPT_DEFAULT = 'if [ ! -f /var/svc/provision_esdc ]; then   ' \
                                  'touch /var/svc/provision_esdc;   ' \
                                  '/usr/sbin/mdata-get root_authorized_keys > /root/.ssh/authorized_keys;   ' \
                                  '/usr/sbin/mdata-get deploy-script > /var/svc/user-deploy-script && ' \
                                  '/usr/bin/bash /var/svc/user-deploy-script;   ' \
                                  '{image_deploy}; ' \
                                  'fi;  ' \
                                  '/usr/sbin/mdata-get startup-script > /var/svc/user-startup-script && ' \
                                  '/usr/bin/bash /var/svc/user-startup-script;  ' \
                                  'exit 0'

VMS_VM_SNAPSHOT_ENABLED = True  # Module
VMS_VM_SNAPSHOT_DEFINE_LIMIT = None  # Maximum number of snapshot definitions (None - unlimited)
VMS_VM_SNAPSHOT_LIMIT_AUTO = None  # Maximum number of automatic snapshots (retention limit) (None - unlimited)
VMS_VM_SNAPSHOT_LIMIT_MANUAL = None  # Maximum number of manual snapshots (None - unlimited)
VMS_VM_SNAPSHOT_LIMIT_MANUAL_DEFAULT = None  # Default limit in forms/serializers
VMS_VM_SNAPSHOT_SIZE_LIMIT = None  # Maximum total size of all (automatic and manual) VM snapshots (None - unlimited)
VMS_VM_SNAPSHOT_SIZE_LIMIT_DEFAULT = None  # Default size limit in forms/serializers
VMS_VM_SNAPSHOT_DC_SIZE_LIMIT = None  # Maximum total size of snapshots in one DC (None - unlimited)

VMS_VM_BACKUP_ENABLED = True  # Module
VMS_VM_BACKUP_FILE_DIR = 'backups/file'  # Backup directory name created on zpool
VMS_VM_BACKUP_DS_DIR = 'backups/ds'  # Backup dataset created on zpool
VMS_VM_BACKUP_MANIFESTS_FILE_DIR = 'backups/manifests/file'  # Manifest directory name created on zpool
VMS_VM_BACKUP_MANIFESTS_DS_DIR = 'backups/manifests/ds'  # Manifest directory name created on zpool
VMS_VM_BACKUP_COMPRESSION_DEFAULT = 0  # None
VMS_VM_BACKUP_DEFINE_LIMIT = None  # Maximum number of backup definitions (None - unlimited)
VMS_VM_BACKUP_LIMIT = None  # Maximum number of backups (retention limit) (None - unlimited)
VMS_VM_BACKUP_DC_SIZE_LIMIT = None  # Maximum total size of backups in one DC (None - unlimited)

VMS_VM_CREATE_EMAIL_SEND = False
VMS_VM_DEPLOY_EMAIL_SEND = True

SECURITY_OWASP_AT_002 = False  # Testing for Account Enumeration and Guessable User Account (False: UX, True: Security)

ACL_ENABLED = True  # Module

# Usernames that clashes with zabbix system usernames etc.
INVALID_USERNAMES = frozenset(['profile', 'Admin', 'provisioner'])


# VVVVVVV        THIS BLOCK SHOULD BE ALWAYS AT THE BOTTOM      VVVVVVVVVVVVVVVV

# Allow any settings to be defined in local_settings.py which is ignored in our
# version control system allowing for settings to be defined (overwritten) per
# machine, and also for security reasons not to store passwords in the VCS.
try:
    from .local_settings import *  # noqa: F401,F403
except ImportError:
    pass

# ESDC :: Third Party Apps Settings
THIRD_PARTY_APPS, THIRD_PARTY_MODULES = collect_third_party_apps_and_settings(locals())

# Updated INSTALLED_APPS with THIRD_PARTY_APPS, make sure nobody fiddle with it.
if THIRD_PARTY_APPS_ENABLED:
    INSTALLED_APPS = tuple(list(INSTALLED_APPS) + THIRD_PARTY_APPS)
    MODULES += THIRD_PARTY_MODULES

MODULES = frozenset(MODULES)

# ^^^^^^^        THIS BLOCK SHOULD BE ALWAYS AT THE BOTTOM      ^^^^^^^^^^^^^^^^
