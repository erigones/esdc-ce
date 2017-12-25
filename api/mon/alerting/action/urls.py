from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.mon.alerting.action.views',

    # base
    # /action - get
    url(r'^$', 'mon_action_list', name='api_mon_action_list'),

    # /action/<action_name> - get, create, set, delete
    url(r'^(?P<action_name>[A-Za-z0-9._-]+)/$', 'mon_action_manage', name='api_mon_action_manage'),
)
