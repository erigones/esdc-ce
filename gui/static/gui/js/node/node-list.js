var NODE_LIST = null;
function NodeList() {
  var self = this;
  var et = new eTable('#node_list');
  var node_search = $('#node_search');
  var controls = {
    'node_status': $('#node_status'),
  };
  this.modal = null;
  this.controls = controls;

  // Check if button is disabled. If not disable it for 0.5 second
  function check_btn(btn) {
    if (btn.hasClass('disabled')) {
      return false;
    }

    btn.addClass('disabled');
    setTimeout(function() {
      btn.removeClass('disabled');
    }, 500);

    return true;
  }

  function node_control_update_all() {
    var selected_node_statuses = _.uniq(_.map(et.selected, function(data, hostname) {
      return $(jq('node_label_' + hostname)).data('status_display');
    }));

    if (!selected_node_statuses.length || _.contains(selected_node_statuses, 'unlicensed')) {
      controls.node_status.addClass('disabled');
    } else {
      controls.node_status.removeClass('disabled');
    }
  }

  this.get_hostnames = function() {
    return _.keys(et.selected);
  };

  this.update = function() {
    et.toggle_controls();
  };

  // Empty selection
  et.controls_hide = function() {
    _.each(controls, function(value, key, list) { value.addClass('disabled'); });
  };

  // Non-empty selection
  et.controls_show = function() {
    _.each(controls, function(value, key, list) { value.removeClass('disabled'); });
    node_control_update_all();
  };

  SIGNALS.view_node_list.dispatch(this);

  // **** Table init ****
  obj_list_sort_js(et.elements.table, [0], {'formatted-num': [5, 6, 7, 8, 9]});
  et.toggle_controls();

  // **** Node search ****
  node_search.focus();
  node_search.keyup(function(e) {
    var val = node_search.val();

    if (val.length > 0) {
      var pattern = new RegExp(val, 'i');

      et.elements.tbody_tr.each(function(i, e) {
        var tr = $(e);
        var hostname = tr.find('span.node_hostname').text();

        if (pattern.test(hostname)) {
          tr.show();
        } else {
          tr.hide();
        }
      });

    } else {
      et.elements.tbody_tr.each(function(i, e) {
        var tr = $(e);
        tr.show();
      });
    }
  }); // Node search

  // **** Node actions ****
  controls.node_status.click(function() {
    self.modal = new obj_form_modal($(this), '#node_status_modal', function(mod, start) {
      if (start) {
        var hostnames = self.get_hostnames();
        $('#id_hostnames_text').html(hostnames.join(', '));
        $('#id_hostnames').val(hostnames);
      }
    });
  });

} // NodeList
