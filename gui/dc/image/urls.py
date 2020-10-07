from django.conf.urls import url

from gui.dc.image.views import dc_image_list, imagestore_list, imagestore_update, dc_image_form, admin_image_form

urlpatterns = [
    url(r'^$', dc_image_list, name='dc_image_list'),
    url(r'^repository/$', imagestore_list, name='imagestore_list'),
    url(r'^repository/(?P<repo>[A-Za-z0-9\._-]+)/$', imagestore_list, name='imagestore_list_repo'),
    url(r'^repository/(?P<repo>[A-Za-z0-9\._-]+)/update/$', imagestore_update, name='imagestore_update'),
    url(r'^form/$', dc_image_form, name='dc_image_form'),
    url(r'^form/admin/$', admin_image_form, name='admin_image_form'),
]
