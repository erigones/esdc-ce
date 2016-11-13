from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.dc.node.views',

    url(r'^$', 'dc_node_list', name='dc_node_list'),
    url(r'^form/$', 'dc_node_form', name='dc_node_form'),
)
