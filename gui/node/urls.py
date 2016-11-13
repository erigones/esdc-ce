from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.node.views',

    url(r'^$', 'node_list', name='node_list'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/$', 'details', name='node_details'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/$', 'define_form', name='node_define_form'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/storages/$', 'storages', name='node_storages'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/storage/form/$', 'storage_form', name='node_storage_form'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/images/$', 'images', name='node_images'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/images/(?P<zpool>[A-Za-z0-9\._-]+)/$',
        'images_zpool', name='node_images_zpool'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/servers/(?P<zpool>[A-Za-z0-9\._-]+)$', 'vms', name='node_vms_zpool'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/servers/$', 'vms', name='node_vms'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backups/$', 'backups', name='node_backups'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backups/form/$', 'backup_form', name='node_backup_form'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backups/list/$', 'backup_list', name='node_backup_list'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backups/list/(?P<vm_hostname>[A-Za-z0-9\._-]+)/$',
        'backup_list', name='node_vm_backup_list'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/monitoring/$', 'monitoring', name='node_monitoring'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/tasklog/$', 'tasklog', name='node_tasklog'),
)
