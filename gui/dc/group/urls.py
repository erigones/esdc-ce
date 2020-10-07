from django.conf.urls import url

from gui.dc.group.views import dc_group_list, dc_group_form, admin_group_form

urlpatterns = [
    url(r'^$', dc_group_list, name='dc_group_list'),
    url(r'^form/$', dc_group_form, name='dc_group_form'),
    url(r'^form/admin/$', admin_group_form, name='admin_group_form'),
]
