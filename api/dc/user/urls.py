from django.urls import path, re_path

from api.dc.user.views import dc_user_list, dc_user

urlpatterns = [
    # /user - get
    path('', dc_user_list, name='api_dc_user_list'),
    # /user/<name> - get
    re_path(r'^(?P<username>[A-Za-z0-9@.+_-]+)/$', dc_user, name='api_dc_user'),
]
