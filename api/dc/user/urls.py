from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.dc.user.views',

    # /user - get
    url(r'^$', 'dc_user_list', name='api_dc_user_list'),
    # /user/<name> - get
    url(r'^(?P<username>[A-Za-z0-9\@\._-]+)/$', 'dc_user', name='api_dc_user'),
)
