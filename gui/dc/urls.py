from django.urls import path, re_path, include

from gui.dc.views import dc_list, dc_form, dc_switch_form, dc_vm_details, dc_vm_backup, dc_dc_settings

urlpatterns = [
    # dc (base)
    path('', dc_list, name='dc_list'),
    path('form/', dc_form, name='dc_form'),
    # dc base + settings
    path('settings/', include('gui.dc.base.urls')),
    # node
    path('node/', include('gui.dc.node.urls')),
    # storage
    path('storage/', include('gui.dc.storage.urls')),
    # network
    path('network/', include('gui.dc.network.urls')),
    # image
    path('image/', include('gui.dc.image.urls')),
    # image
    path('template/', include('gui.dc.template.urls')),
    # iso
    path('iso/', include('gui.dc.iso.urls')),
    # dns
    path('dns/', include('gui.dc.dns.urls')),
    # user
    path('user/', include('gui.dc.user.urls')),
    # group
    path('group/', include('gui.dc.group.urls')),
    # dc switch
    path('switch/', dc_switch_form, name='dc_switch_form'),
    # DC redirect to VM details
    re_path(r'^switch/(?P<dc>[A-Za-z0-9\._-]+)/server/(?P<hostname>[A-Za-z0-9\._-]+)/$', dc_vm_details,
        name='dc_vm_details'),
    # DC redirect to VM backups
    re_path(r'^switch/(?P<dc>[A-Za-z0-9\._-]+)/server/(?P<hostname>[A-Za-z0-9\._-]+)/backup/$', dc_vm_backup,
        name='dc_vm_backup'),
    # DC redirect do DC settings
    re_path(r'^switch/(?P<dc>[A-Za-z0-9\._-]+)/settings/$', dc_dc_settings, name='dc_dc_settings'),
    path('switch/dc-settings/', dc_dc_settings, name='dc_default_settings'),
]
