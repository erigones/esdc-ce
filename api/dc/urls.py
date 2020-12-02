from django.urls import path, re_path, include
from django.conf import settings

from api.dc.views import dc_list, dc_manage, dc_settings

urlpatterns = [
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/iso/', include('api.dc.iso.urls')),
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/image/', include('api.dc.image.urls')),
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/network/', include('api.dc.network.urls')),
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/template/', include('api.dc.template.urls')),
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/storage/', include('api.dc.storage.urls')),
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/node/', include('api.dc.node.urls')),
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/vm/', include('api.vm.urls')),
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/task/', include('api.task.urls')),
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/user/', include('api.dc.user.urls')),
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/group/', include('api.dc.group.urls')),
]

urlpatterns += [
    # /dc - get
    path('', dc_list, name='api_dc_list'),
    # /dc/<name> - get, create, set, delete
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/$', dc_manage, name='api_dc_manage'),
    # /dc/<name>/settings - get, set
    re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/settings/$', dc_settings, name='api_dc_settings'),
]

if settings.DNS_ENABLED:
    urlpatterns += [re_path(r'^(?P<dc>[A-Za-z0-9\._-]+)/domain/', include('api.dc.domain.urls'))]
