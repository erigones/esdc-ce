var NODE_LIST = null;
function NodeList() {
  var et = new eTable('#node_list');
  var check_list = new CheckList();
  var node_search = $('#node_search');
  var controls = {};
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

  this.get_hostnames = function() {
    return _.keys(et.selected);
  };

  // Empty selection
  et.controls_hide = function() {
    _.each(controls, function(value, key, list) { value.addClass('disabled'); });
  };

  // Non-empty selection
  et.controls_show = function() {
    _.each(controls, function(value, key, list) { value.removeClass('disabled'); });
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
} // NodeList
