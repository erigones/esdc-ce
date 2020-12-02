from django.urls import path, re_path

from api.mon.alerting.action.views import mon_action_list, mon_action_manage

urlpatterns = [
    # base
    # /action - get
    path('', mon_action_list, name='api_mon_action_list'),

    # /action/<action_name> - get, create, set, delete
    re_path(r'^(?P<action_name>[A-Za-z0-9._-]+)/$', mon_action_manage, name='api_mon_action_manage'),
]
