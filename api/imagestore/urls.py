from django.conf.urls import url

from api.imagestore.views import imagestore_image_list, imagestore_image_manage, imagestore_list, imagestore_manage

urlpatterns = [
    # base
    # /imagestore - get, set
    url(r'^$', imagestore_list, name='api_imagestore_list'),
    # /imagestore/<name> - get, set
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', imagestore_manage, name='api_imagestore_manage'),

    # image
    # /imagestore/<name>/image - get
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/image/$', imagestore_image_list, name='api_imagestore_list'),
    # /imagestore/<name>/image/<uuid> - get, create
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/image/(?P<uuid>[a-z0-9-]+)/$', imagestore_image_manage,
        name='api_imagestore_image_manage'),
]
