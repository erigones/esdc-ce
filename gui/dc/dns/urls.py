from django.urls import path, re_path

from gui.dc.dns.views import dc_domain_list, dc_domain_form, dc_domain_record_list, admin_domain_form, \
    domain_record_form

urlpatterns = [
    path('', dc_domain_list, name='dc_domain_list'),
    path('form/dc/', dc_domain_form, name='dc_domain_form'),
    path('form/admin/', admin_domain_form, name='admin_domain_form'),
    path('records/', dc_domain_record_list, name='dc_domain_record_list'),
    re_path(r'^domain/(?P<name>[A-Za-z0-9\._/-]+)/record/form/$', domain_record_form, name='domain_record_form'),
]
