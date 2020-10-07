from django.conf.urls import url

from gui.dc.network.views import dc_network_list, dc_network_form, admin_network_form, dc_network_ip_list, \
    network_ip_form, dc_subnet_ip_list

urlpatterns = [
    url(r'^$', dc_network_list, name='dc_network_list'),
    url(r'^form/dc/$', dc_network_form, name='dc_network_form'),
    url(r'^form/admin/$', admin_network_form, name='admin_network_form'),
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/ip/$', dc_network_ip_list, name='dc_network_ip_list'),
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/ip/form/$', network_ip_form, name='network_ip_form'),
    url(r'^(?P<network>[0-9\.]+)/(?P<netmask>[0-9]+)/(?P<vlan_id>[0-9]+)/ip/$', dc_subnet_ip_list,
        name='dc_subnet_ip_list'),
]
