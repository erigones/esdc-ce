from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.dc.template.views',

    url(r'^$', 'dc_template_list', name='dc_template_list'),
    url(r'^form/$', 'dc_template_form', name='dc_template_form'),
)
