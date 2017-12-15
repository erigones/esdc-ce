/*
 * Universal Zabbix functions (used by mon_alert_list)
 */

var MONITORING_ALERTS = null;

function MonitoringAlerts(view_url) {
  this.view_url = view_url;

  this.is_displayed = function() {
    return Boolean($('#alert_list').length);
  };

  this.update = function(filter, result) {

    if (typeof(result) === 'undefined') {
      // NO result, we dont have task yet!
      // Create task and wait for callback with result.
      if (SOCKET.socket.connected) {
        show_loading_screen(gettext('Getting data from Zabbix'), true);
      } else {
        $(".alert-list-table-msg").html(
          'Socket IO needs to be connected in order to get the alert list.<br />Please do not force refresh otherwise this page won\'t work, rather click on ALERTS in menu.'
        );
      }
      mon_get_alerts(filter);
    } else {
      // result contain actual alerts data, but we don't care!
      // We render them via Django and call AJAX to load the table content.
      if (result.status == "SUCCESS") {
        // This is called on esio SUCCESS and CACHE, we might handle cache more inteligently...
        ajax('GET', this.view_url, ATIMEOUT, function(data, textStatus, jqXHR) {
          if (jqXHR.status == 200) {
            $("#alert-list-table").html(data);
          } else {
            $(".alert-list-table-msg").html(textStatus);
          }
        }, filter);

      } else {
        // Something is not alright, this is called on esio FAILED (API error)
        notify('error', _sererror_from_result(result.result));
      }
      hide_loading_screen();
    }
  };
} // mon_Alerts: Zabbix alerts!

function alert_update(filter, result) {
  if(MONITORING_ALERTS && MONITORING_ALERTS.is_displayed()) {
    MONITORING_ALERTS.update(filter, result);
  }
}

function alert_init(view_url, filter) {
  MONITORING_ALERTS = new MonitoringAlerts(view_url);
  MONITORING_ALERTS.update(filter);
}