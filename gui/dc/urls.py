from django.conf.urls import patterns, url, include

urlpatterns = patterns(
    'gui.dc.views',

    # dc (base)
    url(r'^$', 'dc_list', name='dc_list'),
    url(r'^form/$', 'dc_form', name='dc_form'),
    # dc base + settings
    url(r'^settings/', include('gui.dc.base.urls')),
    # node
    url(r'^node/', include('gui.dc.node.urls')),
    # storage
    url(r'^storage/', include('gui.dc.storage.urls')),
    # network
    url(r'^network/', include('gui.dc.network.urls')),
    # image
    url(r'^image/', include('gui.dc.image.urls')),
    # image
    url(r'^template/', include('gui.dc.template.urls')),
    # iso
    url(r'^iso/', include('gui.dc.iso.urls')),
    # dns
    url(r'^dns/', include('gui.dc.dns.urls')),
    # user
    url(r'^user/', include('gui.dc.user.urls')),
    # group
    url(r'^group/', include('gui.dc.group.urls')),
    # dc switch
    url(r'^switch/$', 'dc_switch_form', name='dc_switch_form'),
    # DC redirect to VM details
    url(r'^switch/(?P<dc>[A-Za-z0-9\._-]+)/server/(?P<hostname>[A-Za-z0-9\._-]+)/$', 'dc_vm_details',
        name='dc_vm_details'),
    # DC redirect to VM backups
    url(r'^switch/(?P<dc>[A-Za-z0-9\._-]+)/server/(?P<hostname>[A-Za-z0-9\._-]+)/backup/$', 'dc_vm_backup',
        name='dc_vm_backup'),
    # DC redirect do DC settings
    url(r'^switch/(?P<dc>[A-Za-z0-9\._-]+)/settings/$', 'dc_dc_settings',
        name='dc_dc_settings'),
    url(r'^switch/dc-settings/$', 'dc_dc_settings',
        name='dc_default_settings'),
)
