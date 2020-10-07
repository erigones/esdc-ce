from django.conf.urls import url

from api.mon.alerting.views import mon_alert_list

urlpatterns = [
    # /mon/alert - get
    url(r'^', mon_alert_list, name='api_mon_alert_list')
]