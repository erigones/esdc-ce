from django.conf.urls import url

from api.network.views import net_ip, net_list, net_manage, net_ip_list, net_vm_list, subnet_ip_list
urlpatterns = [
    # base
    # /network - get
    url(r'^$', net_list, name='api_net_list'),

    # ip
    # /network/ip/<subnet> - get
    url(r'^ip/$', subnet_ip_list, name='api_ip_list'),
    url(r'^ip/(?P<subnet>[0-9\./]+)/$', subnet_ip_list, name='api_subnet_ip_list'),

    # base
    # /network/<name> - get, create, set, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', net_manage, name='api_net_manage'),

    # ip
    # /network/<name>/ip - get
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/ip/$', net_ip_list, name='api_net_ip_list'),
    # /network/<name>/ip/<ip> - get, create, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/ip/(?P<ip>[0-9\.]+)/$', net_ip, name='api_net_ip'),

    # vm
    # /network/<name>/vm - get
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/vm/$', net_vm_list, name='api_net_vm_list'),
]
