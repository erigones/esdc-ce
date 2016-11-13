from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.dc.group.views',

    # /group - get
    url(r'^$', 'dc_group_list', name='api_dc_group_list'),
    # /group/<name> - get, post, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', 'dc_group', name='api_dc_group'),
)
