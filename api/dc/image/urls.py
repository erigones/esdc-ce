from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.dc.image.views',

    # /image - get
    url(r'^$', 'dc_image_list', name='api_dc_image_list'),
    # /image/<name> - get, create, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', 'dc_image', name='api_dc_image'),
)
