from api.mon.base.tasks import mon_alert_list
from api.mon.base.serializers import AlertSerializer
from api.mon.base.api_views import _MonBaseView


class MonAlertView(_MonBaseView):
    api_view_name = 'mon_alert_list'
    mgmt_task = mon_alert_list
    ser_class = AlertSerializer

    def get(self):
        if 'show_all' in self.data and self.data['show_all']:
            self.dc_bound = False

        return super(MonAlertView, self).get()
