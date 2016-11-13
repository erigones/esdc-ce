from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.dc.node.views',

    # /node - get
    url(r'^$', 'dc_node_list', name='api_dc_node_list'),
    # /node/<hostname> - get, create, set, delete
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/$', 'dc_node', name='api_dc_node'),
)
