from django.urls import path, re_path

from api.dc.node.views import dc_node_list, dc_node

urlpatterns = [
    # /node - get
    path('', dc_node_list, name='api_dc_node_list'),
    # /node/<hostname> - get, create, set, delete
    re_path(r'^(?P<hostname>[A-Za-z0-9\._-]+)/$', dc_node, name='api_dc_node'),
]
