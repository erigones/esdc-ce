from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.profile.views',

    # Profile pages, with url prefix: accounts/profile
    url(r'^$', 'index', name='profile'),
    url(r'^api_keys/$', 'apikeys', name='profile_apikeys'),
    url(r'^update/$', 'update', name='profile_update'),
    url(r'^password/$', 'password_change', name='profile_password'),
    url(r'^activate/$', 'activation', name='profile_activation'),
    url(r'^ssh_key/(?P<action>add|delete)/$', 'sshkey', name='profile_sshkey'),
    url(r'^impersonate/user/(?P<username>[A-Za-z0-9@.+_-]+)/$', 'start_impersonation', name='start_impersonation'),
    url(r'^impersonate/cancel/$', 'stop_impersonation', name='stop_impersonation'),
)
