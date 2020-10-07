from django.conf.urls import url

from gui.dc.dns.views import dc_domain_list, dc_domain_form, dc_domain_record_list, admin_domain_form, \
    domain_record_form

urlpatterns = [
    url(r'^$', dc_domain_list, name='dc_domain_list'),
    url(r'^form/dc/$', dc_domain_form, name='dc_domain_form'),
    url(r'^form/admin/$', admin_domain_form, name='admin_domain_form'),
    url(r'^records/$', dc_domain_record_list, name='dc_domain_record_list'),
    url(r'^domain/(?P<name>[A-Za-z0-9\._/-]+)/record/form/$', domain_record_form, name='domain_record_form'),
]
