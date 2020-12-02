from django.urls import path, re_path

from api.mon.base.views import mon_template_list, mon_hostgroup_list, mon_hostgroup_manage
urlpatterns = [
    # /mon/template - get
    path('template/', mon_template_list, name='api_mon_template_list'),

    # /mon/hostgroup - get
    path('hostgroup/', mon_hostgroup_list, name='api_mon_hostgroup_list'),

    # /mon/hostgroup/<hostgroup_name> - get, create, set, delete
    re_path(r'^hostgroup/(?P<hostgroup_name>[A-Za-z0-9._-]+)/$', mon_hostgroup_manage, name='api_mon_hostgroup_manage'),
]
