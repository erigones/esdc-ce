from django.urls import path, re_path

from api.dc.group.views import dc_group_list, dc_group

urlpatterns = [
    # /group - get
    path('', dc_group_list, name='api_dc_group_list'),
    # /group/<name> - get, post, delete
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/$', dc_group, name='api_dc_group'),
]
