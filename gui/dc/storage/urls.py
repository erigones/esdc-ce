from django.urls import path

from gui.dc.storage.views import dc_storage_form, dc_storage_list

urlpatterns = [
    path('', dc_storage_list, name='dc_storage_list'),
    path('form/', dc_storage_form, name='dc_storage_form'),
]
