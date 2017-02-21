from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.mon.node.views',

    # /mon/node/<hostname>/sla/(yyyymm) - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/sla/(?P<yyyymm>\d{5,6})/$',
        'mon_node_sla', name='api_mon_node_sla'),
    # /mon/node/<hostname>/history/(graph) - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/history/(?P<graph>[A-Za-z0-9\._-]+)/$',
        'mon_node_history', name='api_mon_node_history'),
)
