from django.urls import path, re_path

from api.system.views import system_service_status, system_service_status_list, system_node_version_list, \
    system_node_version, system_node_service_status_list, system_node_update, system_node_service_status, \
    system_node_logs, system_version, system_stats, system_update, system_logs, system_settings_ssl_certificate

urlpatterns = [
    # service
    # /system/service/status - get
    path('service/status/', system_service_status_list, name='system_service_status_list'),
    # /system/service/<name>/status - get
    re_path(r'^service/(?P<name>[A-Za-z0-9:\._-]+)/status/$', system_service_status, name='system_service_status'),
    # /system/node/version - get
    path('node/version/', system_node_version_list, name='system_node_version_list'),
    # /system/node/<hostname>/version - get
    re_path(r'^node/(?P<hostname>[A-Za-z0-9\._-]+)/version/$', system_node_version, name='system_node_version'),
    # /system/node/<hostname>/service/<name>/status - get
    re_path(r'^node/(?P<hostname>[A-Za-z0-9\._-]+)/service/status/$', system_node_service_status_list,
            name='system_node_service_status_list'),
    # /system/node/<hostname>/service/status - get
    re_path(r'^node/(?P<hostname>[A-Za-z0-9\._-]+)/service/(?P<name>[A-Za-z0-9:\._-]+)/status/$',
            system_node_service_status, name='system_node_service_status'),
    # /system/node/<hostname>/update - set
    re_path(r'^node/(?P<hostname>[A-Za-z0-9\._-]+)/update/$', system_node_update, name='system_node_update'),
    # /system/node/<hostname>/logs - get
    re_path(r'^node/(?P<hostname>[A-Za-z0-9\._-]+)/logs/$', system_node_logs, name='system_node_logs'),
    # /system/version - get
    path('version/', system_version, name='system_version'),
    # /system/update - set
    path('update/', system_update, name='system_update'),
    # /system/logs - get
    path('logs/', system_logs, name='system_logs'),
    # /system/settings/ssl-certificate - set
    path('settings/ssl-certificate/', system_settings_ssl_certificate, name='system_settings_ssl_certificate'),
    # /system/stats
    path('stats/', system_stats, name='system_stats'),
]
