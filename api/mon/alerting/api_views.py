from api.mon.base.api_views import MonBaseView
from api.mon.alerting.serializers import AlertSerializer
from api.mon.alerting.tasks import mon_alert_list


class MonAlertView(MonBaseView):
    api_view_name = 'mon_alert_list'
    mgmt_task = mon_alert_list
    ser_class = AlertSerializer

    def get(self):
        if 'dc_unbound' in self.data and self.data['dc_unbound']:
            self.dc_bound = False

        return super(MonAlertView, self).get()
