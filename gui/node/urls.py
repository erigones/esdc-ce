from django.urls import path, re_path

from gui.node.views import node_list, status_form, details, define_form, storages, storage_form, images, images_zpool, \
    vms, backup_definitions, backups, backup_form, backup_list, monitoring, tasklog

urlpatterns = [
    path('', node_list, name='node_list'),
    path('status/form/', status_form, name='node_status_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/$', details, name='node_details'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/$', define_form, name='node_define_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/storages/$', storages, name='node_storages'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/storage/form/$', storage_form, name='node_storage_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/images/$', images, name='node_images'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/images/(?P<zpool>[A-Za-z0-9\._-]+)/$',
            images_zpool, name='node_images_zpool'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/servers/(?P<zpool>[A-Za-z0-9\._-]+)$', vms, name='node_vms_zpool'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/servers/$', vms, name='node_vms'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backup-definitions/$', backup_definitions, name='node_backup_definitions'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backups/$', backups, name='node_backups'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backups/form/$', backup_form, name='node_backup_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backups/list/$', backup_list, name='node_backup_list'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backups/list/(?P<vm_hostname>[A-Za-z0-9\._-]+)/$',
            backup_list, name='node_vm_backup_list'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/monitoring/$', monitoring, name='node_monitoring'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/monitoring/(?P<graph_type>[A-Za-z0-9-]+)/$',
            monitoring, name='node_monitoring_graphs'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/tasklog/$', tasklog, name='node_tasklog'),
]
