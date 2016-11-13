from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.dc.user.views',

    url(r'^$', 'dc_user_list', name='dc_user_list'),
    url(r'^form/$', 'dc_user_modal_form', name='dc_user_modal_form'),
    url(r'^(?P<username>[A-Za-z0-9\@\._-]+)/profile/$', 'dc_user_profile', name='dc_user_profile'),
    url(r'^(?P<username>[A-Za-z0-9\@\._-]+)/profile/api_keys/$', 'dc_user_profile_apikeys',
        name='dc_user_profile_apikeys'),
    url(r'^(?P<username>[A-Za-z0-9\@\._-]+)/profile/form/$', 'dc_user_profile_form', name='dc_user_profile_form'),
    url(r'^(?P<username>[A-Za-z0-9\@\._-]+)/profile/password/form/$', 'dc_user_profile_password_modal_form',
        name='dc_user_profile_password_modal_form'),
    url(r'^(?P<username>[A-Za-z0-9\@\._-]+)/profile/ssh_key/(?P<action>add|delete)/form/$',
        'dc_user_profile_sshkey_modal_form', name='dc_user_profile_sshkey_modal_form'),
)
