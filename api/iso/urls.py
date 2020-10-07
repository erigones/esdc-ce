from django.conf.urls import url

from api.iso.views import iso_manage, iso_list

urlpatterns = [
    # base
    # /iso - get
    url(r'^$', iso_list, name='api_iso_list'),
    # /iso/<name> - get, create, set, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', iso_manage, name='api_iso_manage'),
]
