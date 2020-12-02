from django.urls import path, re_path

from api.dc.image.views import dc_image, dc_image_list

urlpatterns = [
    # /image - get
    path('', dc_image_list, name='api_dc_image_list'),
    # /image/<name> - get, create, delete
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/$', dc_image, name='api_dc_image'),
]
