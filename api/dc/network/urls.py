from django.urls import path, re_path

from api.dc.network.views import dc_network, dc_network_list, dc_network_ip_list

urlpatterns = [
    # /network - get
    path('', dc_network_list, name='api_dc_network_list'),
    # /network/<name> - get, create, delete
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/$', dc_network, name='api_dc_network'),
    # /network/<name>/ip - get
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/ip/$', dc_network_ip_list, name='api_dc_network_ip_list'),
]
