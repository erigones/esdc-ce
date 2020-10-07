from django.conf.urls import url

from api.dc.storage.views import dc_storage_list, dc_storage

urlpatterns = [
    # /storage - get
    url(r'^$', dc_storage_list, name='api_dc_storage_list'),
    # /storage/<zpool_node> - get, create, delete
    url(r'^(?P<zpool_node>[A-Za-z0-9\._-]+@[A-Za-z0-9\._-]+)/$', dc_storage, name='api_dc_storage'),
]
