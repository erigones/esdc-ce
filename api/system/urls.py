from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.system.views',

    # service
    # /system/service/status - get
    url(r'^service/status/$', 'system_service_status_list', name='system_service_status_list'),
    # /system/service/<name>/status - get
    url(r'^service/(?P<name>[A-Za-z0-9:\._-]+)/status/$', 'system_service_status', name='system_service_status'),
    # /system/node/version - get
    url(r'^node/version/$', 'system_node_version_list', name='system_node_version_list'),
    # /system/node/<hostname>/version - get
    url(r'^node/(?P<hostname>[A-Za-z0-9\._-]+)/version/$', 'system_node_version', name='system_node_version'),
    # /system/node/<hostname>/service/<name>/status - get
    url(r'^node/(?P<hostname>[A-Za-z0-9\._-]+)/service/status/$',
        'system_node_service_status_list', name='system_node_service_status_list'),
    # /system/node/<hostname>/service/status - get
    url(r'^node/(?P<hostname>[A-Za-z0-9\._-]+)/service/(?P<name>[A-Za-z0-9:\._-]+)/status/$',
        'system_node_service_status', name='system_node_service_status'),
    # /system/node/<hostname>/update - set
    url(r'^node/(?P<hostname>[A-Za-z0-9\._-]+)/update/$', 'system_node_update', name='system_node_update'),
    # /system/node/<hostname>/logs - get
    url(r'^node/(?P<hostname>[A-Za-z0-9\._-]+)/logs/$', 'system_node_logs', name='system_node_logs'),
    # /system/version - get
    url(r'^version/$', 'system_version', name='system_version'),
    # /system/update - set
    url(r'^update/$', 'system_update', name='system_update'),
    # /system/logs - get
    url(r'^logs/$', 'system_logs', name='system_logs'),
    # /system/settings/ssl-certificate - set
    url(r'^settings/ssl-certificate/$', 'system_settings_ssl_certificate', name='system_settings_ssl_certificate'),
)
