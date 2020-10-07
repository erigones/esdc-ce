from django.conf.urls import url

from api.dc.user.views import dc_user_list, dc_user

urlpatterns = [
    # /user - get
    url(r'^$', dc_user_list, name='api_dc_user_list'),
    # /user/<name> - get
    url(r'^(?P<username>[A-Za-z0-9@.+_-]+)/$', dc_user, name='api_dc_user'),
]
