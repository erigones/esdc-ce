from django.urls import path, re_path

from api.imagestore.views import imagestore_image_list, imagestore_image_manage, imagestore_list, imagestore_manage

urlpatterns = [
    # base
    # /imagestore - get, set
    path('', imagestore_list, name='api_imagestore_list'),
    # /imagestore/<name> - get, set
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/$', imagestore_manage, name='api_imagestore_manage'),

    # image
    # /imagestore/<name>/image - get
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/image/$', imagestore_image_list, name='api_imagestore_list'),
    # /imagestore/<name>/image/<uuid> - get, create
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/image/(?P<uuid>[a-z0-9-]+)/$', imagestore_image_manage,
            name='api_imagestore_image_manage'),
]
