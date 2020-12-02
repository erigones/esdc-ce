from django.urls import path, re_path

from api.dns.views import dns_record_list, dns_record, dns_domain_list, dns_domain

urlpatterns = [
    # records
    # /dns/domain/<name>/record - get
    re_path(r'^domain/(?P<name>[A-Za-z0-9\._/-]+)/record/$', dns_record_list, name='api_dns_record_list'),
    # /dns/domain/<name>/record/<record_id> - get, create, set, delete
    re_path(r'^domain/(?P<name>[A-Za-z0-9\._/-]+)/record/(?P<record_id>\d+)/$', dns_record, name='api_dns_record'),

    # domains
    # /dns/domain - get
    path('domain/', dns_domain_list, name='api_dns_domain_list'),
    # /dns/domain/<name> - get, create, set, delete
    re_path(r'^domain/(?P<name>[A-Za-z0-9\._/-]+)/$', dns_domain, name='api_dns_domain'),
]
