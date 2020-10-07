from django.conf.urls import url, include
from django.conf import settings

from api.node.views import node_list, node_define, node_image, node_image_list, node_define_list, node_manage, \
    node_storage, node_sysinfo, node_storage_list, node_vm_list, node_vm_backup_list, node_vm_define_backup_list, \
    node_vm_snapshot_list, harvest_vm

urlpatterns = [
    # storage
    # /node/<hostname>/storage - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/storage/$', node_storage_list, name='api_node_storage_list'),
    # /node/<hostname>/storage/<zpool> - get, create, set, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/storage/(?P<zpool>[A-Za-z0-9\._-]+)/$', node_storage,
        name='api_node_storage'),

    # image
    # /node/<hostname>/storage/<zpool>/image - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/storage/(?P<zpool>[A-Za-z0-9\._-]+)/image/$', node_image_list,
        name='api_node_image_list'),
    # /node/<hostname>/storage/<zpool>/image/<name> - get, create, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/storage/(?P<zpool>[A-Za-z0-9\._-]+)/image/(?P<name>[A-Za-z0-9\._-]+)/$',
        node_image, name='api_node_image'),

    # define
    # /node/define - get
    url(r'^define/$', node_define_list, name='api_node_define_list'),
    # /node/<hostname>/define - get, set, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/$', node_define, name='api_node_define'),

    # snapshot
    # /node/<hostname>/snapshot/<zpool> - get, set
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/storage/(?P<zpool>[A-Za-z0-9\._-]+)/snapshot/$', node_vm_snapshot_list,
        name='api_node_vm_snapshot_list'),

    # backup
    # /node/<hostname>/backup - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backup/$', node_vm_backup_list, name='api_node_vm_backup_list'),

    # define backup
    # /node/<hostname>/define/backup - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/backup/$', node_vm_define_backup_list,
        name='api_node_vm_define_backup_list'),

    # vm
    # /node/<hostname>/vm-harvest - create (dc aware)
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/vm-harvest/$', harvest_vm, name='api_harvest_vm'),
    # /node/<hostname>/vm - get (dc unaware)
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/vm/$', node_vm_list, name='api_vm_list'),

    # base
    # /node - get
    url(r'^$', node_list, name='api_node_list'),
    # /node/<hostname> - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/$', node_manage, name='api_node_manage'),

    # sysinfo
    # /node/<hostname>/sysinfo - put
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/sysinfo/$', node_sysinfo, name='api_node_sysinfo'),
]

if settings.MON_ZABBIX_ENABLED:
    urlpatterns += [url(r'^', include('api.mon.node.urls'))]
