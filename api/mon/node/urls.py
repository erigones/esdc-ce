from django.urls import re_path

from api.mon.node.views import mon_node_sla, mon_node_history

urlpatterns = [
    # /mon/node/<hostname>/sla/(yyyymm) - get
    re_path(r'^(?P<hostname>[A-Za-z0-9._-]+)/sla/(?P<yyyymm>\d{5,6})/$', mon_node_sla, name='api_mon_node_sla'),
    # /mon/node/<hostname>/history/(graph) - get
    re_path(r'^(?P<hostname>[A-Za-z0-9._-]+)/history/(?P<graph>[A-Za-z0-9._-]+)/$', mon_node_history,
            name='api_mon_node_history'),
]
