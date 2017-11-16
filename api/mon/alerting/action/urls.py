from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.mon.alerting.action.views',

    # base
    # /action - get
    url(r'^$', 'action_list', name='api_mon_action_list'),

    # /action/<name> - get, create, set, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', 'action_manage', name='api_action_manage'),
)
