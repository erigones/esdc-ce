from django.urls import path

from api.mon.alerting.views import mon_alert_list

urlpatterns = [
    # /mon/alert - get
    path('', mon_alert_list, name='api_mon_alert_list')
]