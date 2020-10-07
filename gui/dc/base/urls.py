from django.conf.urls import url

from gui.dc.base.views import dc_settings_form, dc_settings, dc_settings_table

urlpatterns = [
    url(r'^form/$', dc_settings_form, name='dc_settings_form'),
    url(r'^table/$', dc_settings_table, name='dc_settings_table'),
    url(r'^$', dc_settings, name='dc_settings'),
]
