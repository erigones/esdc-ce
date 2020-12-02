from django.urls import path, re_path
from django.conf import settings

from api.accounts.views import api_login, api_logout, user_list, user_manage, user_apikeys, userprofile_list, \
    userprofile_manage, sshkey_manage, sshkey_list

urlpatterns = [
    path('login/', api_login, name='api_accounts_login'),
    path('logout/', api_logout, name='api_accounts_logout'),

    # /accounts/user - get
    path('user/', user_list, name='api_user_list'),
    # /accounts/user/profile - get
    path('user/profile/', userprofile_list, name='api_userprofile_list'),
    # /accounts/user/<username> - get, create, delete
    re_path(r'^user/(?P<username>[A-Za-z0-9@.+_-]+)/$', user_manage, name='api_user_manage'),
    # /accounts/user/<username>/apikeys - get, set
    re_path(r'^user/(?P<username>[A-Za-z0-9@.+_-]+)/apikeys/$', user_apikeys, name='api_use_apikeys'),
    # /accounts/user/<username>/profile - get, set
    re_path(r'^user/(?P<username>[A-Za-z0-9@.+_-]+)/profile/$', userprofile_manage, name='api_userprofile_manage'),
    # /accounts/user/<username>/sshkey - get
    re_path(r'^user/(?P<username>[A-Za-z0-9@.+_-]+)/sshkey/$', sshkey_list, name='api_sshkey_list'),
    # /accounts/user/<username>/sshkey/<title> - get, create, delete
    re_path(r'^user/(?P<username>[A-Za-z0-9@.+_-]+)/sshkey/(?P<title>[A-Za-z0-9@.+_-]+)/$', sshkey_manage,
            name='api_sshkey_manage'),
]

if settings.ACL_ENABLED:
    from api.accounts.views import permission_list, permission_manage, group_list, group_manage

    urlpatterns += [
        # /accounts/permission - get
        path('permission/', permission_list, name='api_permission_list'),
        # /accounts/permission/<name> - get
        re_path(r'^permission/(?P<name>[A-Za-z0-9\._-]+)/$', permission_manage, name='api_permission_manage'),

        # /accounts/group - get
        path('group/', group_list, name='api_group_list'),
        # /accounts/group/<name> - get, TODO: create, set, delete
        re_path(r'^group/(?P<name>[A-Za-z0-9\._-]+)/$', group_manage, name='api_group_manage'),
    ]
