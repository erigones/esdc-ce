from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.template.views',

    # base
    # /template - get
    url(r'^$', 'template_list', name='api_template_list'),
    # /template/<name> - get, create, set, delete
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/$', 'template_manage', name='api_template_manage'),

    # vm
    # /template/<name>/vm - get
    url(r'^(?P<name>[A-Za-z0-9\._-]+)/vm/$', 'template_vm_list', name='api_template_vm_list'),
)
