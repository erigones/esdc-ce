from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.mon.views',

    url(r'^alerts/$', 'alert_list', name='mon_alert_list'),
    url(r'^alert/list/$', 'alert_list_table', name='alert_list_table'),
    url(r'^hostgroups/$', 'hostgroup_list', name='mon_hostgroup_list'),
    url(r'^templates/$', 'template_list', name='mon_template_list'),
    url(r'^actions/$', 'action_list', name='mon_action_list'),
    url(r'^webchecks/$', 'webcheck_list', name='mon_webcheck_list'),
    url(r'^zabbix/$', 'mon_server_redirect', name='mon_server_redirect'),
)
