from django.urls import path, re_path

from gui.dc.image.views import dc_image_list, imagestore_list, imagestore_update, dc_image_form, admin_image_form

urlpatterns = [
    path('', dc_image_list, name='dc_image_list'),
    path('repository/', imagestore_list, name='imagestore_list'),
    re_path(r'^repository/(?P<repo>[A-Za-z0-9\._-]+)/$', imagestore_list, name='imagestore_list_repo'),
    re_path(r'^repository/(?P<repo>[A-Za-z0-9\._-]+)/update/$', imagestore_update, name='imagestore_update'),
    path('form/', dc_image_form, name='dc_image_form'),
    path('form/admin/', admin_image_form, name='admin_image_form'),
]
