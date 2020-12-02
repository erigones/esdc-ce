from django.urls import path, re_path

from api.dc.template.views import dc_template_list, dc_template

urlpatterns = [

    # /template - get
    path('', dc_template_list, name='api_dc_template_list'),
    # /template/<name> - get, create, delete
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/$', dc_template, name='api_dc_template'),
]
