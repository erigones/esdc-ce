from django.conf.urls import patterns, url

# noinspection PyPep8
urlpatterns = patterns(
    'gui.vm.replication.views',
    url(r'^vm/(?P<hostname>[A-Za-z0-9\._-]+)/replication/$', 'replication_form', name='vm_replication_form'),
)
