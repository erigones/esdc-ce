from django.conf.urls import patterns, url, include
from django.conf import settings

urlpatterns = patterns(
    'api.vm.views',

    # other
    # /vm/<hostname>/screenshot - get, create
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/screenshot/$',
        'vm_screenshot', name='api_vm_screenshot'),

    # qga
    # /vm/<hostname>/qga/<command> - set
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/qga/(?P<command>[A-Za-z0-9_-]+)/$',
        'vm_qga', name='api_vm_qga'),

    # migrate
    # /vm/<hostname>/migrate/dc - set
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/migrate/dc/$',
        'vm_dc', name='api_vm_dc'),
    # /vm/<hostname>/migrate - set
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/migrate/$',
        'vm_migrate', name='api_vm_migrate'),

    # define snapshot report
    url(r'^define/snapshot/$',
        'vm_define_snapshot_list_all', name='api_vm_define_snapshot_list_all'),

    # snapshot
    # /vm/<hostname>/snapshot - get, set, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/snapshot/$',
        'vm_snapshot_list', name='api_vm_snapshot_list'),
    # /vm/<hostname>/snapshot/<snapname> - get, create, set, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/snapshot/(?P<snapname>[A-Za-z0-9\._-]+)/$',
        'vm_snapshot', name='api_vm_snapshot'),

    # status
    # /vm/status - get
    url(r'^status/$',
        'vm_status_list', name='api_vm_status_list'),
    # /vm/<hostname>/status - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/status/$',
        'vm_status', name='api_vm_status'),
    # /vm/<hostname>/status/{current|start|stop|restart} - get, set
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/status/(?P<action>(current|start|stop|reboot))/$',
        'vm_status', name='api_vm_status'),

    # define
    # /vm/define - get
    url(r'^define/$',
        'vm_define_list', name='api_vm_define_list'),
    # /vm/<hostname>/define - get, create, set, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/$',
        'vm_define', name='api_vm_define'),
    # /vm/<hostname>/define/revert - set
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/(undo|revert)/$',
        'vm_define_revert', name='api_vm_define_revert'),
    # /vm/<hostname>/define/disk - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/disk/$',
        'vm_define_disk_list', name='api_vm_define_disk_list'),
    # /vm/<hostname>/define/disk/<disk_id> - get, create, set, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/disk/(?P<disk_id>\d)/$',
        'vm_define_disk', name='api_vm_define_disk'),
    # /vm/<hostname>/define/nic - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/nic/$',
        'vm_define_nic_list', name='api_vm_define_nic_list'),
    # /vm/<hostname>/define/nic/<nic_id> - get, create, set, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/nic/(?P<nic_id>\d)/$',
        'vm_define_nic', name='api_vm_define_nic'),

    # define snapshot
    # /vm/<hostname>/define/snapshot - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/snapshot/$',
        'vm_define_snapshot_list', name='api_vm_define_snapshot_list'),
    # /vm/<hostname>/define/snapshot/<snapdef> - get, create, set, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/snapshot/(?P<snapdef>[A-Za-z0-9\._-]+)/$',
        'vm_define_snapshot', name='api_vm_define_snapshot'),

    # image from snapshot
    # /vm/<hostname>/snapshot/<snapname>/image/<name> - create
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/snapshot/(?P<snapname>[A-Za-z0-9\._-]+)/image/(?P<name>[A-Za-z0-9\._-]+)/$',
        'image_snapshot', name='api_image_snapshot'),

    # base
    # /vm - get
    url(r'^$',
        'vm_list', name='api_vm_list'),
    # /vm/<hostname> - get, create, set, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/$',
        'vm_manage', name='api_vm_manage'),
)

if settings.VMS_VM_BACKUP_ENABLED:
    urlpatterns += patterns(
        'api.vm.views',

        # define backup report
        url(r'^define/backup/$',
            'vm_define_backup_list_all', name='api_vm_define_backup_list_all'),
        # backup
        # /vm/<hostname>/backup - get, delete
        url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backup/$',
            'vm_backup_list', name='api_vm_backup_list'),
        # /vm/<hostname>/backup/<bkpname> - get, create, set, delete
        url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backup/(?P<bkpname>[A-Za-z0-9\._-]+)/$',
            'vm_backup', name='api_vm_backup'),
        # define backup
        # /vm/<hostname>/define/backup - get
        url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/backup/$',
            'vm_define_backup_list', name='api_vm_define_backup_list'),
        # /vm/<hostname>/define/backup/<bkpdef> - get, create, set, delete
        url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/define/backup/(?P<bkpdef>[A-Za-z0-9\._-]+)/$',
            'vm_define_backup', name='api_vm_define_backup'),
    )

if settings.MON_ZABBIX_ENABLED:
    urlpatterns += patterns('', url(r'^', include('api.mon.vm.urls')))
