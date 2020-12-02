from django.urls import path, re_path

from api.dc.domain.views import dc_domain, dc_domain_list

urlpatterns = [
    # /iso - get
    path('', dc_domain_list, name='api_dc_domain_list'),
    # /iso/<name> - get, create, delete
    re_path(r'^(?P<name>[A-Za-z0-9\._/-]+)/$', dc_domain, name='api_dc_domain'),
]
