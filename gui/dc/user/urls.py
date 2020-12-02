from django.urls import path, re_path

from gui.dc.user.views import dc_user_list, dc_user_modal_form, dc_user_profile, dc_user_profile_apikeys, \
    dc_user_profile_form, dc_user_profile_password_modal_form, dc_user_profile_sshkey_modal_form

urlpatterns = [
    path('', dc_user_list, name='dc_user_list'),
    path('form/', dc_user_modal_form, name='dc_user_modal_form'),
    re_path(r'^(?P<username>[A-Za-z0-9@.+_-]+)/profile/$', dc_user_profile, name='dc_user_profile'),
    re_path(r'^(?P<username>[A-Za-z0-9@.+_-]+)/profile/api_keys/$', dc_user_profile_apikeys,
            name='dc_user_profile_apikeys'),
    re_path(r'^(?P<username>[A-Za-z0-9@.+_-]+)/profile/form/$', dc_user_profile_form, name='dc_user_profile_form'),
    re_path(r'^(?P<username>[A-Za-z0-9@.+_-]+)/profile/password/form/$', dc_user_profile_password_modal_form,
            name='dc_user_profile_password_modal_form'),
    re_path(r'^(?P<username>[A-Za-z0-9@.+_-]+)/profile/ssh_key/(?P<action>add|delete)/form/$',
            dc_user_profile_sshkey_modal_form, name='dc_user_profile_sshkey_modal_form'),
]
