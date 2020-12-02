from django.urls import re_path

from api.vm.replica.views import vm_replica, vm_replica_list, vm_replica_failover, vm_replica_reinit
# noinspection PyPep8
urlpatterns = [
    # manage replication
    # /vm/<hostname_or_uuid>/replica - get
    re_path(r'^api/vm/(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/replica/$', vm_replica_list, name='api_vm_replica_list'),
    # /vm/<hostname_or_uuid>/replica/<repname> - get, create, set, delete
    re_path(r'^api/vm/(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/replica/(?P<repname>[A-Za-z0-9\._-]+)/$', vm_replica,
            name='api_vm_replica'),
    # /vm/<hostname_or_uuid>/replica/failover - set
    re_path(r'^api/vm/(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/replica/(?P<repname>[A-Za-z0-9\._-]+)/failover/$',
            vm_replica_failover, name='api_vm_replica_failover'),
    # /vm/<hostname_or_uuid>/replica/reinit - set
    re_path(r'^api/vm/(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/replica/(?P<repname>[A-Za-z0-9\._-]+)/reinit/$',
            vm_replica_reinit, name='api_vm_replica_reinit'),
]
