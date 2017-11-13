/*
 * Universal Zabbix functions (used by mon_alert_list)
 */

var ZAPI = null;

function mon_ZAPI(view_name, hostname) {
  this.view_name = view_name;
  // TODO: add ability to filter by hostname (and other filters, eg. date)
  this.hostname = hostname;

  var self = this;

  var list_table_html = function(msg) {
    return '<table class="box table table-striped table-condensed table-responsive" id="tasklog-table"><thead></thead>' +
           '<tbody id="tasklog" class="nowrap"><tr><td colspan="8">' +
           '<p class="msg">' + msg + '</p></td></tr></tbody><tfoot></tfoot></table>'
  };

  this.update = function(yyyymm, result) {
    if (typeof(result) === 'undefined') {
      // NO result, we dont have task yet!
      // Create task and wait for callback with result.
      if (SOCKET.socket.connected) {
        show_loading_screen('Getting data from Zabbix', true);
      } else {
        $("#alert-list-table").html(
          list_table_html('Socket IO needs to be connected in order to get the alert list.<br />Please do not force refresh otherwise this page won\'t work, rather click on ALERTS in menu.')
        );
      }
      mon_get_alerts(view_name, hostname, yyyymm);
    } else {
      // result contain actual alerts data, but we don't care!
      // We render them via Django and call AJAX to load the table content.
      ajax('GET', '/monitoring/retrieve-alerts/', ATIMEOUT, function(data, textStatus, jqXHR) {
        if (jqXHR.status == 200) {
          $("#alert-list-table").html(data);
        } else {
          $("#alert-list-table").html(list_table_html(textStatus));
        }
      });
      hide_loading_screen();
    }
  };
} // mon_ZAPI: Zabbix alerts!

function alert_update(view_name, hostname, yyyymm, result) {
  ZAPI.update(yyyymm, result);
}

function alert_init(view_name, hostname, yyyymm) {
  ZAPI = new mon_ZAPI(view_name, hostname);
  ZAPI.update(yyyymm);
}