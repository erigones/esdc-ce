/*
 * Universal SLA functions (used by mon_vm_sla and mon_node_sla)
 */

var SLA = null;

function mon_SLA(view_name, hostname) {
  this.view_name = view_name;
  this.hostname = hostname;
  this.sla = $(jq('mon_sla_' + hostname));  // escaping dots in hostname

  var self = this;
  var chooser_timer = null;
  var value = this.sla.find('span.sla_value');
  var date = this.sla.find('span.sla_date');
  var buttons = this.sla.find('a');

  // Update date value and disabled/enable prev/next buttons
  function _update_chooser(date_value) {
    if (typeof(date_value) === 'undefined') {
      date_value = date.html();
    } else {
      date.html(date_value);
    }

    if (date.data('max') == date_value) {
      buttons.last().addClass('disabled');
    }
    if (date.data('min') == date_value) {
      buttons.first().addClass('disabled');
    }
  }

  /*
   * Add links to VM's SLA month prev/next buttons
   */
  this.activate_links = function() {
    _update_chooser();

    buttons.each(function() {
      $(this).click(function(e) {
        var btn = $(this);
        e.preventDefault();

        if (btn.hasClass('disabled')) {
          return false;
        }

        var _date = date.html().split('/');
        var _month = parseInt(_date[0]);

        if (btn.hasClass('sla_next')) {
          _month++;
        } else if (btn.hasClass('sla_prev')) {
          _month--;
        }

        var d = new Date(parseInt(_date[1]), _month - 1, 1);
        var year = String(d.getFullYear());
        var month = pad(String(d.getMonth() + 1), 2);

        _update_chooser(month + '/' + year);
        self.update(year + month);

        return false;
      });
    });
  };

  /*
   * Get SLA and update SLA element
   */
  this.update = function(yyyymm, result) {
    if (!self.sla.length) {
      return;
    }

    if (typeof(result) === 'undefined') { // without result => create task
      value.addClass('loading-gif');
      value.html('&nbsp;&nbsp;&nbsp;&nbsp;');

      clearTimeout(chooser_timer);
      chooser_timer = setTimeout(function() {
        buttons.addClass('disabled');
        // emit
        if (get_sla(view_name, hostname, yyyymm) === null) { // emit never happened
          value.removeClass('loading-gif');
          value.html('---');
        }
      }, 1000);

    } else { // result => update UI
      buttons.removeClass('disabled');
      value.removeClass('loading-gif');

      if (result) {
        value.html(result.sla + ' %');
      } else {
        value.html(gettext('N/A'));
      }

      // also update the chooser date/links (just in case)
      _update_chooser(String(yyyymm).slice(4) + '/' + String(yyyymm).slice(0,4));
    }
  };

} // SLA

function sla_update(view_name, hostname, yyyymm, result) {
  if (SLA && SLA.hostname == hostname && SLA.view_name == view_name) {
    SLA.update(yyyymm, result);
  }
}

function sla_init(view_name, hostname, yyyymm) {
  SLA = new mon_SLA(view_name, hostname);
  SLA.update(yyyymm);
  SLA.activate_links();
}
