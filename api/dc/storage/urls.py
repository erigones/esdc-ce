from django.urls import path, re_path

from api.dc.storage.views import dc_storage_list, dc_storage

urlpatterns = [
    # /storage - get
    path('', dc_storage_list, name='api_dc_storage_list'),
    # /storage/<zpool_node> - get, create, delete
    re_path(r'^(?P<zpool_node>[A-Za-z0-9\._-]+@[A-Za-z0-9\._-]+)/$', dc_storage, name='api_dc_storage'),
]
