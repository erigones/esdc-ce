from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.dc.image.views',

    url(r'^$', 'dc_image_list', name='dc_image_list'),
    url(r'^repository/$', 'imagestore_list', name='imagestore_list'),
    url(r'^repository/(?P<repo>[A-Za-z0-9\._-]+)/$', 'imagestore_list', name='imagestore_list_repo'),
    url(r'^repository/(?P<repo>[A-Za-z0-9\._-]+)/update/$', 'imagestore_update', name='imagestore_update'),
    url(r'^form/$', 'dc_image_form', name='dc_image_form'),
    url(r'^form/admin/$', 'admin_image_form', name='admin_image_form'),
)
