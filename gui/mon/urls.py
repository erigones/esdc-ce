from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.mon.views',

    url(r'^$', 'monitoring_server', name='monitoring_server_redirect'),
)
