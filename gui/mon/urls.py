from django.urls import path

from gui.mon.views import alert_list, alert_list_table, hostgroup_list, template_list, action_list, webcheck_list, \
    mon_server_redirect

urlpatterns = [
    path('alerts/', alert_list, name='mon_alert_list'),
    path('alert/list/', alert_list_table, name='alert_list_table'),
    path('hostgroups/', hostgroup_list, name='mon_hostgroup_list'),
    path('templates/', template_list, name='mon_template_list'),
    path('actions/', action_list, name='mon_action_list'),
    path('webchecks/', webcheck_list, name='mon_webcheck_list'),
    path('zabbix/', mon_server_redirect, name='mon_server_redirect'),
]
