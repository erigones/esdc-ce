from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.mon.views',

    url(r'^$', 'actions_list', name='mon_actions_list'),
    url(r'^redirect$', 'monitoring_server', name='monitoring_server_redirect'),
    url(r'^add-action/$', 'add_action', name='mon_action_add'),
    url(r'^action-(?P<action_id>[0-9]+)/$', 'action_detail', name='mon_action_detail'),

)
