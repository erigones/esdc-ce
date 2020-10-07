from django.conf.urls import url

from gui.dc.iso.views import dc_iso_list, dc_iso_form, admin_iso_form

urlpatterns = [
    url(r'^$', dc_iso_list, name='dc_iso_list'),
    url(r'^form/$', dc_iso_form, name='dc_iso_form'),
    url(r'^form/admin/$', admin_iso_form, name='admin_iso_form'),
]
