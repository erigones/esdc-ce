from django.urls import path, re_path

from api.dc.iso.views import dc_iso_list, dc_iso

urlpatterns = [
    # /iso - get
    path('', dc_iso_list, name='api_dc_iso_list'),
    # /iso/<name> - get, create, delete
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/$', dc_iso, name='api_dc_iso'),
]
