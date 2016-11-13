from django.conf.urls import patterns, url, include
from django.conf import settings

urlpatterns = patterns(
    '',

    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/iso/', include('api.dc.iso.urls')),
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/image/', include('api.dc.image.urls')),
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/network/', include('api.dc.network.urls')),
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/template/', include('api.dc.template.urls')),
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/storage/', include('api.dc.storage.urls')),
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/node/', include('api.dc.node.urls')),
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/vm/', include('api.vm.urls')),
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/task/', include('api.task.urls')),
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/user/', include('api.dc.user.urls')),
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/group/', include('api.dc.group.urls')),
)

urlpatterns += patterns(
    'api.dc.views',

    # /dc - get
    url(r'^$', 'dc_list', name='api_dc_list'),
    # /dc/<name> - get, create, set, delete
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/$', 'dc_manage', name='api_dc_manage'),
    # /dc/<name>/settings - get, set
    url(r'^(?P<dc>[A-Za-z0-9\._-]+)/settings/$', 'dc_settings', name='api_dc_settings'),
)

if settings.DNS_ENABLED:
    urlpatterns += patterns('', url(r'^(?P<dc>[A-Za-z0-9\._-]+)/domain/', include('api.dc.domain.urls')))
