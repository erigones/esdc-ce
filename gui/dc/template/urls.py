from django.urls import path

from gui.dc.template.views import dc_template_list, dc_template_form

urlpatterns = [
    path('', dc_template_list, name='dc_template_list'),
    path('form/', dc_template_form, name='dc_template_form'),
]
