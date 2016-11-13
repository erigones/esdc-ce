from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.dc.storage.views',

    url(r'^$', 'dc_storage_list', name='dc_storage_list'),
    url(r'^form/$', 'dc_storage_form', name='dc_storage_form'),
)
