from django.conf.urls import patterns, url

# noinspection PyPep8
urlpatterns = patterns(
    'api.vm.replica.views',
    # manage replication
    # /vm/<hostname_or_uuid>/replica - get
    url(r'^api/vm/(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/replica/$',
        'vm_replica_list', name='api_vm_replica_list'),
    # /vm/<hostname_or_uuid>/replica/<repname> - get, create, set, delete
    url(r'^api/vm/(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/replica/(?P<repname>[A-Za-z0-9\._-]+)/$',
        'vm_replica', name='api_vm_replica'),
    # /vm/<hostname_or_uuid>/replica/failover - set
    url(r'^api/vm/(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/replica/(?P<repname>[A-Za-z0-9\._-]+)/failover/$',
        'vm_replica_failover', name='api_vm_replica_failover'),
    # /vm/<hostname_or_uuid>/replica/reinit - set
    url(r'^api/vm/(?P<hostname_or_uuid>[A-Za-z0-9\._-]+)/replica/(?P<repname>[A-Za-z0-9\._-]+)/reinit/$',
        'vm_replica_reinit', name='api_vm_replica_reinit'),
)
