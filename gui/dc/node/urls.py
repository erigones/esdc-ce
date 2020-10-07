from django.conf.urls import url

from gui.dc.node.views import dc_node_list, dc_node_form

urlpatterns = [
    url(r'^$', dc_node_list, name='dc_node_list'),
    url(r'^form/$', dc_node_form, name='dc_node_form'),
]
