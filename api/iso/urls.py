from django.urls import path, re_path

from api.iso.views import iso_manage, iso_list

urlpatterns = [
    # base
    # /iso - get
    path('', iso_list, name='api_iso_list'),
    # /iso/<name> - get, create, set, delete
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/$', iso_manage, name='api_iso_manage'),
]
