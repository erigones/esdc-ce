from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.dc.base.views',

    url(r'^form/$', 'dc_settings_form', name='dc_settings_form'),
    url(r'^table/$', 'dc_settings_table', name='dc_settings_table'),
    url(r'^$', 'dc_settings', name='dc_settings'),
)
