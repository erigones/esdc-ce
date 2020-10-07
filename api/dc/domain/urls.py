from django.conf.urls import url

from api.dc.domain.views import dc_domain, dc_domain_list

urlpatterns = [
    # /iso - get
    url(r'^$', dc_domain_list, name='api_dc_domain_list'),
    # /iso/<name> - get, create, delete
    url(r'^(?P<name>[A-Za-z0-9\._/-]+)/$', dc_domain, name='api_dc_domain'),
]
