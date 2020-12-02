from django.urls import path, re_path

from gui.profile.views import index, apikeys, update, password_change, activation, sshkey, start_impersonation, \
    stop_impersonation

urlpatterns = [
    # Profile pages, with url prefix: accounts/profile
    path('', index, name='profile'),
    path('api_keys/', apikeys, name='profile_apikeys'),
    path('update/', update, name='profile_update'),
    path('password/', password_change, name='profile_password'),
    path('activate/', activation, name='profile_activation'),
    re_path(r'^ssh_key/(?P<action>add|delete)/$', sshkey, name='profile_sshkey'),
    re_path(r'^impersonate/user/(?P<username>[A-Za-z0-9@.+_-]+)/$', start_impersonation, name='start_impersonation'),
    path('impersonate/cancel/', stop_impersonation, name='stop_impersonation'),
]
