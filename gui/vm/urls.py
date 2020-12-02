from django.urls import path, re_path

from gui.vm.views import my_list, multi_settings_form, vm_import_sample, vm_export, add_settings_form, \
    add_import_form, add, details, console, vnc, snapshot, snapshot_form, snapshot_list, snapshot_define_form, \
    snapshot_image_form, backup, backup_form, backup_list, backup_define_form, ptr_form, disk_settings_form, \
    nic_settings_form, undo_settings, settings_form, set_installed, monitoring, tasklog

urlpatterns = [
    path('', my_list, name='vm_list'),
    path('settings/', multi_settings_form, name='vm_multi_settings_form'),
    path('import/sample/', vm_import_sample, name='vm_import_sample'),
    path('export/', vm_export, name='vm_export'),

    path('add/settings/', add_settings_form, name='vm_add_settings_form'),
    path('add/import/', add_import_form, name='vm_add_import_form'),
    path('add/', add, name='vm_add'),

    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/$', details, name='vm_details'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/console/$', console, name='vm_console'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/console/vnc/$', vnc, name='vnc'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/snapshot/$', snapshot, name='vm_snapshot'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/snapshot/form/$', snapshot_form, name='vm_snapshot_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/snapshot/list/$', snapshot_list, name='vm_snapshot_list'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/snapshot/define/form/$', snapshot_define_form,
            name='vm_snapshot_define_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/snapshot/image/form/$', snapshot_image_form, name='vm_snapshot_image_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backup/$', backup, name='vm_backup'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backup/form/$', backup_form, name='vm_backup_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backup/list/$', backup_list, name='vm_backup_list'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/backup/define/form/$', backup_define_form, name='vm_backup_define_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/nic/(?P<nic_id>\d{1,2})/ptr/$', ptr_form, name='vm_ptr_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/settings/nic/$', nic_settings_form, name='vm_nic_settings_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/settings/disk/$', disk_settings_form, name='vm_disk_settings_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/settings/undo/$', undo_settings, name='vm_undo_settings'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/settings/$', settings_form, name='vm_settings_form'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/installed/$', set_installed, name='vm_installed'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/monitoring/$', monitoring, name='vm_monitoring'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/monitoring/(?P<graph_type>[A-Za-z0-9-]+)/$', monitoring,
            name='vm_monitoring_graphs'),
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/tasklog/$', tasklog, name='vm_tasklog'),
]
