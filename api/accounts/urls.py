from django.conf.urls import patterns, url
from django.conf import settings

urlpatterns = patterns(
    'api.accounts.views',

    url(r'^login/$', 'api_login', name='api_accounts_login'),
    url(r'^logout/$', 'api_logout', name='api_accounts_logout'),

    # /accounts/user - get
    url(r'^user/$', 'user_list', name='api_user_list'),
    # /accounts/user/profile - get
    url(r'^user/profile/$', 'userprofile_list', name='api_userprofile_list'),
    # /accounts/user/<username> - get, create, delete
    url(r'^user/(?P<username>[A-Za-z0-9@.+_-]+)/$', 'user_manage', name='api_user_manage'),
    # /accounts/user/<username>/apikeys - get, set
    url(r'^user/(?P<username>[A-Za-z0-9@.+_-]+)/apikeys/$', 'user_apikeys', name='api_use_apikeys'),
    # /accounts/user/<username>/profile - get, set
    url(r'^user/(?P<username>[A-Za-z0-9@.+_-]+)/profile/$', 'userprofile_manage', name='api_userprofile_manage'),
    # /accounts/user/<username>/sshkey - get
    url(r'^user/(?P<username>[A-Za-z0-9@.+_-]+)/sshkey/$', 'sshkey_list', name='api_sshkey_list'),
    # /accounts/user/<username>/sshkey/<title> - get, create, delete
    url(r'^user/(?P<username>[A-Za-z0-9@.+_-]+)/sshkey/(?P<title>[A-Za-z0-9@.+_-]+)/$', 'sshkey_manage',
        name='api_sshkey_manage'),
)

if settings.ACL_ENABLED:
    urlpatterns += patterns(
        'api.accounts.views',

        # /accounts/permission - get
        url(r'^permission/$', 'permission_list', name='api_permission_list'),
        # /accounts/permission/<name> - get
        url(r'^permission/(?P<name>[A-Za-z0-9\._-]+)/$', 'permission_manage', name='api_permission_manage'),

        # /accounts/group - get
        url(r'^group/$', 'group_list', name='api_group_list'),
        # /accounts/group/<name> - get, TODO: create, set, delete
        url(r'^group/(?P<name>[A-Za-z0-9\._-]+)/$', 'group_manage', name='api_group_manage'),
    )
