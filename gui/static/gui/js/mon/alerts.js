var MONITORING_ALERTS = null;

/*
 * Monitoring alerts (used by mon_alert_list)
 */
function MonitoringAlerts(filter, csrf_token) {
  var alert_table = $('#alert-list-table');
  var initialized = false;
  var nosort = [3];

  if (filter.show_events) {
    nosort.push(-1);
  }

  this.is_displayed = function() {
    return initialized && Boolean($(alert_table.selector).length);
  };

  this.init = function() {
    // Initial call -> create task and wait for callback with result
    initialized = true;
    return mon_get_alerts(filter);
  };

  this.update = function(result, error) {
    initialized = false;

    if (result === null) {
      // result is null when something has failed
      if (error) {
        alert_table.find('#alert-msg').addClass('alert alert-error');
        alert_table.find('#alert-msg p').text(error);
      }
    } else {
      // result contains actual alerts data, but we don't care
      // We render them via Django and call AJAX to load the table contents
      ajax('POST', alert_table.data('source'), ATIMEOUT, function(data) {
        alert_table.html(data);
        obj_list_sort_js(alert_table.find('table'), nosort, {'sort-tag': [0, 1], 'icon-tag': [4]});
      }, {'alert_filter': JSON.stringify(filter), 'csrfmiddlewaretoken': csrf_token});
    }
  };
}  // MonitoringAlerts


function alert_update(result, error) {
  if (MONITORING_ALERTS && MONITORING_ALERTS.is_displayed()) {
    hide_loading_screen();
    MONITORING_ALERTS.update(result, error);
  }
}

function alert_init(filter, csrf_token) {
  MONITORING_ALERTS = new MonitoringAlerts(filter, csrf_token);

  mon_initialize(MONITORING_ALERTS.init);
}
