from django.urls import path

from gui.dc.base.views import dc_settings_form, dc_settings, dc_settings_table

urlpatterns = [
    path('form/', dc_settings_form, name='dc_settings_form'),
    path('table/', dc_settings_table, name='dc_settings_table'),
    path('', dc_settings, name='dc_settings'),
]
