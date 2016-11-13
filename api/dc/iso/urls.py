from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.dc.iso.views',

    # /iso - get
    url(r'^$', 'dc_iso_list', name='api_dc_iso_list'),
    # /iso/<name> - get, create, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', 'dc_iso', name='api_dc_iso'),
)
