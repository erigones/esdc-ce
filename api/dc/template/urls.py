from django.conf.urls import url

from api.dc.template.views import dc_template_list, dc_template

urlpatterns = [

    # /template - get
    url(r'^$', dc_template_list, name='api_dc_template_list'),
    # /template/<name> - get, create, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', dc_template, name='api_dc_template'),
]
