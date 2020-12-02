from django.urls import path

from gui.dc.iso.views import dc_iso_list, dc_iso_form, admin_iso_form

urlpatterns = [
    path('', dc_iso_list, name='dc_iso_list'),
    path('form/', dc_iso_form, name='dc_iso_form'),
    path('form/admin/', admin_iso_form, name='admin_iso_form'),
]
