from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.dc.group.views',

    url(r'^$', 'dc_group_list', name='dc_group_list'),
    url(r'^form/$', 'dc_group_form', name='dc_group_form'),
    url(r'^form/admin/$', 'admin_group_form', name='admin_group_form'),
)
