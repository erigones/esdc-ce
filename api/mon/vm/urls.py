from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.mon.vm.views',

    # /mon/vm/<hostname>/monitoring - get, set
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/monitoring/$',
        'mon_vm_define', name='api_mon_vm_define'),
    # /mon/vm/<hostname>/sla/(yyyymm) - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/sla/(?P<yyyymm>\d{5,6})/$',
        'mon_vm_sla', name='api_mon_vm_sla'),
    # /mon/vm/<hostname>/history/(graph) - get
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/history/(?P<graph>[A-Za-z0-9\._-]+)/$',
        'mon_vm_history', name='api_mon_vm_history'),
    url(r'^(?P<hostname>[A-Za-z0-9\._-]+)/history/(?P<graph>[A-Za-z0-9\._-]+)/(?P<item_id>\d)/$',
        'mon_vm_history', name='api_mon_vm_history'),
)
