from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.mon.vm.views',

    # /mon/vm/<hostname_or_uuid>/monitoring - get, set
    url(r'^(?P<hostname_or_uuid>[A-Za-z0-9._-]+)/monitoring/$',
        'mon_vm_define', name='api_mon_vm_define'),
    # /mon/vm/<hostname_or_uuid>/sla/(yyyymm) - get
    url(r'^(?P<hostname_or_uuid>[A-Za-z0-9._-]+)/sla/(?P<yyyymm>\d{5,6})/$',
        'mon_vm_sla', name='api_mon_vm_sla'),
    # /mon/vm/<hostname_or_uuid>/history/(graph) - get
    url(r'^(?P<hostname_or_uuid>[A-Za-z0-9._-]+)/history/(?P<graph>[A-Za-z0-9._-]+)/$',
        'mon_vm_history', name='api_mon_vm_history'),
)
