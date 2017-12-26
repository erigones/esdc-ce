from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.mon.base.views',

    # /mon/template - get
    url(r'^template/$', 'mon_template_list', name='api_mon_template_list'),

    # /mon/hostgroup - get
    url(r'^hostgroup/$', 'mon_hostgroup_list', name='api_mon_hostgroup_list'),

    # /mon/hostgroup/<hostgroup_name> - get, create, set, delete
    url(r'^hostgroup/(?P<hostgroup_name>[A-Za-z0-9._-]+)/$', 'mon_hostgroup_manage', name='api_mon_hostgroup_manage'),
)
