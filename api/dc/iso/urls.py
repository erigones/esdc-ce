from django.conf.urls import url

from api.dc.iso.views import dc_iso_list, dc_iso

urlpatterns = [
    # /iso - get
    url(r'^$', dc_iso_list, name='api_dc_iso_list'),
    # /iso/<name> - get, create, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', dc_iso, name='api_dc_iso'),
]
