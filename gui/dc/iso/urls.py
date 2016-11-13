from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.dc.iso.views',

    url(r'^$', 'dc_iso_list', name='dc_iso_list'),
    url(r'^form/$', 'dc_iso_form', name='dc_iso_form'),
    url(r'^form/admin/$', 'admin_iso_form', name='admin_iso_form'),
)
