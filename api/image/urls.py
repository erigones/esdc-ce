from django.conf.urls import url

from api.image.views import image_list, image_manage, image_vm_list

urlpatterns = [
    # base
    # /image - get
    url(r'^$', image_list, name='api_image_list'),
    # /image/<name> - get, create, set, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', image_manage, name='api_image_manage'),

    # vm
    # /image/<name>/vm - get
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/vm/$', image_vm_list, name='api_image_vm_list'),
]
