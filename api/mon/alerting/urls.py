from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.mon.alerting.views',

    # /mon/alert - get
    url(r'^', 'mon_alert_list', name='api_mon_alert_list')
)
