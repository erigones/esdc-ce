from django.urls import re_path

from gui.vm.replication.views import replication_form

# noinspection PyPep8
urlpatterns = [
    re_path(r'^vm/(?P<hostname>[A-Za-z0-9\._-]+)/replication/$', replication_form, name='vm_replication_form'),
]
