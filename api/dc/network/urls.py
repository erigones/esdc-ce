from django.conf.urls import url

from api.dc.network.views import dc_network, dc_network_list, dc_network_ip_list

urlpatterns = [
    # /network - get
    url(r'^$', dc_network_list, name='api_dc_network_list'),
    # /network/<name> - get, create, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', dc_network, name='api_dc_network'),
    # /network/<name>/ip - get
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/ip/$', dc_network_ip_list, name='api_dc_network_ip_list'),
]
