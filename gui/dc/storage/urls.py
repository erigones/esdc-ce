from django.conf.urls import url

from gui.dc.storage.views import dc_storage_form, dc_storage_list

urlpatterns = [
    url(r'^$', dc_storage_list, name='dc_storage_list'),
    url(r'^form/$', dc_storage_form, name='dc_storage_form'),
]
