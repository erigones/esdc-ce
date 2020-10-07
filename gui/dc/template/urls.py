from django.conf.urls import url

from gui.dc.template.views import dc_template_list, dc_template_form

urlpatterns = [
    url(r'^$', dc_template_list, name='dc_template_list'),
    url(r'^form/$', dc_template_form, name='dc_template_form'),
]
