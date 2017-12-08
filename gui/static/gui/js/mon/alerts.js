/*
 * Universal Zabbix functions (used by mon_alert_list)
 */

var MONITORING_ALERTS = null;

function mon_Alerts(view_url) {
  this.view_url = view_url;

  this.update = function(filter, result) {

    if (typeof(result) === 'undefined') {
      // NO result, we dont have task yet!
      // Create task and wait for callback with result.
      if (SOCKET.socket.connected) {
        show_loading_screen('Getting data from Zabbix', true);
      } else {
        $(".msg").html(
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
            $(".msg").html(textStatus);
          }
        }, filter);

      } else {
        // Something is not alright, loop throught result and alert messages!
        // This is called on esio FAILED (API error)
        for (var key in result.result) {
          if (result.result.hasOwnProperty(key)) {
            for(var i=0; i < result.result[key].length; ++i){
              notify('error', result.result[key][i]);
            }
          }
        }
      }
      hide_loading_screen();
    }
  };
} // mon_Alerts: Zabbix alerts!

function alert_update(filter, result) {
  MONITORING_ALERTS.update(filter, result);
}

function alert_init(view_name, filter) {
  MONITORING_ALERTS = new mon_Alerts(view_name);
  MONITORING_ALERTS.update(filter);
}