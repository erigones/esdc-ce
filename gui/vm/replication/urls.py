from django.conf.urls import url

from gui.vm.replication.views import replication_form

# noinspection PyPep8
urlpatterns = [
    url(r'^vm/(?P<hostname>[A-Za-z0-9\._-]+)/replication/$', replication_form, name='vm_replication_form'),
]
