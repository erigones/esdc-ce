from django.urls import path, re_path

from api.template.views import template_list, template_manage, template_vm_list

urlpatterns = [
    # base
    # /template - get
    path('', template_list, name='api_template_list'),
    # /template/<name> - get, create, set, delete
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/$', template_manage, name='api_template_manage'),

    # vm
    # /template/<name>/vm - get
    re_path(r'^(?P<name>[A-Za-z0-9\._-]+)/vm/$', template_vm_list, name='api_template_vm_list'),
]
