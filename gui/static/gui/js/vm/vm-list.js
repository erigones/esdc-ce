var VMS = null;
var VMS_TAGS = [];

/*********** ServerListTags singleton object *************/
var ServerListTags = (function() {
  var tags = [];
  var data = null;
  var data_map = null;
  var save_timer = null;
  var elements = {};

  function save_tags(tagstring) {
    clearTimeout(save_timer);

    if (USER_VMS_TAGS == tagstring) {
      return;
    }

    setTimeout(function() {
      USER_VMS_TAGS = tagstring;
      console.log('Saving tags!', USER_VMS_TAGS);
      if (SOCKET.socket.connected) {
        SOCKET.emit('user_vms_tags', USER_VMS_TAGS);
      }
    }, 1000);
  }

  function load_data() { // caching data
    if (data === null) {
      data_map = _.object(VMS_TAGS);
      data = _.keys(data_map);
    }

    return data;
  }

  function filter_vms() {
    if (tags.length === 0) {
      elements.vms_list_left.show();
      if (VMS) {elements.vms_list_main.addClass('visible-by-tag').not('.hidden-by-search').show();}
    } else {
      var q = _.map(tags, function(i) { return '.tag-' + data_map[i]; } ).join('');
      elements.vms_list_left.hide().filter(q).show();
      if (VMS) {
        VMS.reset_server_list();
        elements.vms_list_main.hide().removeClass('visible-by-tag').filter(q).addClass('visible-by-tag').not('.hidden-by-search').show();
      }
    }

    save_tags(tags.join(','));
  }

  function filter_left(current_tags) {
    tags = current_tags;

    // also update main filter chooser
    if (VMS) {
      var q = _.map(tags, function(i) { return '.tag-' + data_map[i]; } ).join(', ');
      elements.vms_tags_main.removeClass('active').filter(q).addClass('active');
    }

    return filter_vms();
  }

  function filter_main(tag, removing) {
    if (removing) {
      tags = _.filter(tags, function(i) { return i != tag; } );
    } else {
      tags.push(tag);
    }

    // always update left filter
    elements.vms_tags_left.select2('val', tags, false);

    return filter_vms();
  }

  return { // public interface
    tags: function() {
      return load_data();
    },

    init: function() {
      data = null;
      data_map = null;
      elements.vms_list_left = $('#sub-menu-list li');
      elements.vms_tags_left = $('#vms_tags');
      elements.vms_list_main = $('#my_server_list_tbody tr');
      elements.vms_tags_main = $('#vms_tag_chooser button');

      // Initialize sub menu tag selector
      elements.vms_tags_left.select2({
        tags: load_data,
        width: '100%',
        createSearchChoice: function() { return null; },
        dropdownCssClass: 'vms_tags tags-select2'
      }).on('change', function(e) { update_submenu(); filter_left(e.val); });

      // Initialize main server list tag buttons
      if ((typeof(VMS) !== 'undefined') && VMS && VMS.is_displayed()) {
        elements.vms_tags_main.click(function() {
          var btn = $(this);
          filter_main(btn.data('tag'), btn.hasClass('active'));
        });
      } else {
        VMS = null;
      }

      // Load current user tags and fire filter change event, which will update both VM lists
      elements.vms_tags_left.select2('val', USER_VMS_TAGS.split(','), true);
    }
  };
})();


/*********** ServerList class *************/
function ServerList(admin) {
  this.dt = null;  // dataTable
  var self = this;
  var server_list = {};
  var elements = {
    'chbox_all':    $('#id_all'),
    'chbox_vms':    $('#my_server_list_tbody input[type="checkbox"]:enabled'),
    'tbody_tr':     $('#my_server_list_tbody tr'),
    'tfoot':        $('#my_server_list_tfoot'),
    'table':        $('#my_server_list'),
    'vms_form':     $('#vms_form'),
    'vms_search':   $('#vms_search'),
    'vms_tags':     $('#vms_tags_big'),
    'vms_control':  $('#vms_control'),
    'vms_selected': $('#vms_selected'),
    'vms_start':    $('#vms_start'),
    'vms_reboot':   $('#vms_reboot'),
    'vms_stop':     $('#vms_stop'),
    'vms_control_modal': $('#vms_control_modal'),
    'vms_export':   $('#vms_export'),
    'vms_iframe_download': $('#vms_iframe_download'),
  };

  if (admin) {
    elements['vms_update'] = $('#vms_update');
    elements['vms_deploy'] = $('#vms_deploy');
    elements['vms_delete'] = $('#vms_delete');
    elements['vms_destroy'] = $('#vms_destroy');
    elements['vms_freeze'] = $('#vms_freeze');
    elements['vms_unfreeze'] = $('#vms_unfreeze');
  }


  /*
   * Initial status of vm_controls
   */
  function vm_control_disable_all() {
    elements.vms_start.addClass('disabled');
    elements.vms_stop.addClass('disabled');
    elements.vms_reboot.addClass('disabled');
    elements.vms_export.addClass('disabled');
    if (admin) {
      elements.vms_update.addClass('disabled').hide();
      elements.vms_deploy.addClass('disabled').hide();
      elements.vms_delete.addClass('disabled').hide();
      elements.vms_destroy.addClass('disabled').hide();
      elements.vms_freeze.addClass('disabled').hide();
      elements.vms_unfreeze.addClass('disabled').hide();
    }
  }

  /*
   * Update vm_controls according to status of all selected servers
   */
  function vm_control_update_all() {
    elements.vms_start.removeClass('disabled');
    elements.vms_reboot.removeClass('disabled');
    elements.vms_stop.removeClass('disabled');
    elements.vms_export.removeClass('disabled');
    if (admin) {
      elements.vms_update.removeClass('disabled').show();
      elements.vms_deploy.removeClass('disabled').show();
      elements.vms_delete.removeClass('disabled').show();
      elements.vms_destroy.removeClass('disabled').show();
      elements.vms_freeze.removeClass('disabled').show();
      elements.vms_unfreeze.removeClass('disabled').show();
    }

    _.each(server_list, function(data, hostname, i) {
      if (data.locked) {
        elements.vms_deploy.addClass('disabled');
        elements.vms_delete.addClass('disabled');
        elements.vms_destroy.addClass('disabled');
      }

      switch(data.status_display) {
        case 'running':
          elements.vms_start.addClass('disabled');
          elements.vms_deploy.addClass('disabled').hide();
          elements.vms_delete.addClass('disabled').hide();
          if (admin) {
            elements.vms_destroy.addClass('disabled');
            elements.vms_unfreeze.addClass('disabled').hide();
          }
          break;

        case 'stopped':
          elements.vms_stop.addClass('disabled');
          elements.vms_reboot.addClass('disabled');
          if (admin) {
            elements.vms_deploy.addClass('disabled').hide();
            elements.vms_delete.addClass('disabled').hide();
            elements.vms_unfreeze.addClass('disabled').hide();
          }
          break;

        case 'stopped-':
        case 'running-':
        case 'frozen-':
        case 'notcreated-':
        case 'stopping':
        case 'notready':
        case 'pending':
        case 'creating':
        case 'deploying':
        case 'unknown':
        case 'error':
          elements.vms_start.addClass('disabled');
          elements.vms_stop.addClass('disabled');
          elements.vms_reboot.addClass('disabled');
          if (admin) {
            elements.vms_update.addClass('disabled');
            elements.vms_deploy.addClass('disabled').hide();
            elements.vms_delete.addClass('disabled').hide();
            elements.vms_destroy.addClass('disabled');
            elements.vms_freeze.addClass('disabled');
            elements.vms_unfreeze.addClass('disabled').hide();
          }
          break;

        case 'notcreated':
          elements.vms_start.addClass('disabled');
          elements.vms_stop.addClass('disabled');
          elements.vms_reboot.addClass('disabled');
          if (admin) {
            elements.vms_update.addClass('disabled').hide();
            elements.vms_destroy.addClass('disabled').hide();
            elements.vms_freeze.addClass('disabled').hide();
            elements.vms_unfreeze.addClass('disabled').hide();
          }
          break;

        case 'frozen':
          elements.vms_start.addClass('disabled');
          elements.vms_stop.addClass('disabled');
          elements.vms_reboot.addClass('disabled');
          if (admin) {
            elements.vms_update.addClass('disabled');
            elements.vms_deploy.addClass('disabled').hide();
            elements.vms_delete.addClass('disabled').hide();
            elements.vms_destroy.addClass('disabled');
            elements.vms_freeze.addClass('disabled').hide();
          }
          break;

        default:
          vm_control_disable_all();
          break;
      }

    });
  }


  /*
   * Show / Hide vm_control according to server_list object
   */
  function toggle_vm_control() {
    // Update selected count
    elements.vms_selected.html(_.size(server_list));

    if ($.isEmptyObject(server_list)) {
      vm_control_disable_all();
      //elements.tfoot.slideUp(400, vm_control_update_all);
    } else {
      vm_control_update_all();
      //elements.tfoot.slideDown(400);
    }
  }

  /*
   * Initialize data table
   */
  function table_init() {
    if (elements.table.find('p.msg').length) { // error message
      return;
    }

    var nosort = [0, 3, 4, -1];
    if (admin) {
      nosort = [0, -1];
    }

    if (elements.table.find('thead tr').length) {
      self.dt = elements.table.dataTable({
        'bProcessing': false,
        'bPaginate': false,
        'bLengthChange': false,
        'bFilter': false,
        'bInfo': false,
        'bSort': true,
        'aoColumnDefs': [
          {'bSortable': false, 'aTargets': nosort},
          {'bSearchable': false, 'aTargets': nosort},
          {'sType': 'formatted-num', 'aTargets': [6, 7, 8]},
        ],
      });
    }
  }

  /*
   * New server list check operation
   */
  this.reset_server_list = function() {
    server_list = {};
    elements.chbox_all.prop('checked', false);
    elements.chbox_vms.prop('checked', false);
    elements.tbody_tr.removeClass('highlight');
    toggle_vm_control();
  };

  /*
   * Update cell in data table
   */
  this.update_cell = function(hostname, column, data) {
    var tr = $(jq('id_' + hostname)).closest('tr');
    var row;

    if (self.dt && tr.length) {
      row = self.dt.fnGetPosition(tr[0]);

      self.dt.fnUpdate(data, row, column);
    }
  };

  /*
   * Reload node column data
   */
  this.refresh_vm_node = function(hostname) {
    var cell = $(jq('vm_node_' + hostname)).closest('td');

    if (cell.length) {
      self.update_cell(hostname, cell.index(), cell.html());
    }
  };

  /*
   * Start all servers in server_list
   */
  function vms_start() {
    _.each(server_list, function(data, hostname, i) {
      vm_start(hostname, false);
    });
    //self.reset_server_list();
  }

  /*
   * Stop all servers in server_list
   */
  function vms_stop(force) {
    _.each(server_list, function(data, hostname, i) {
      vm_stop_or_reboot(hostname, 'stop', force);
    });
    //self.reset_server_list();
  }

  /*
   * Reboot all servers in server_list
   */
  function vms_reboot(force) {
    _.each(server_list, function(data, hostname, i) {
      vm_stop_or_reboot(hostname, 'reboot', force);
    });
    //self.reset_server_list();
  }

  /*
   * Update all servers in server_list
   */
  function vms_update() {
    _.each(server_list, function(data, hostname, i) {
      vm_update(hostname);
    });
    //self.reset_server_list();
  }

  /*
   * Deploy all servers in server_list
   */
  function vms_deploy() {
    _.each(server_list, function(data, hostname, i) {
      vm_create(hostname);
    });
    //self.reset_server_list();
  }

  /*
   * Delete all servers in server_list
   */
  function vms_delete() {
    var post_data = elements.vms_form.serialize() + '&action=delete';

    _.each(server_list, function(data, hostname, i) {
      post_data += '&hostname=' + hostname;
    });

    ajax('POST', elements.vms_form.data('source'), ATIMEOUT, function(data, textStatus, xhr) {
      if (xhr.status == 278) {
        ajax_move(null, xhr.getResponseHeader('Location'));
      }
    }, post_data);

    self.reset_server_list();
  }

  /*
   * Destroy all servers in server_list
   */
  function vms_destroy() {
    _.each(server_list, function(data, hostname, i) {
      vm_delete(hostname);
    });
    //self.reset_server_list();
  }

  /*
   * Freeze/Unfreeze all servers in server_list
   */
  function vms_freeze(freeze, force) {
    _.each(server_list, function(data, hostname, i) {
      vm_freeze(hostname, freeze, force);
    });
    //self.reset_server_list();
  }


  /*
   * Check if button is disabled. If not disable it for 2 seconds
   */
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

  /*
   * **** ADD / DEL ****
   */
  function server(chbox) {
    var tr = chbox.parent().parent().parent();
    var hostname = chbox.attr('id').substring(3);
    var label = $(jq('vm_label_' + hostname));

    this.del = function() {
      chbox.prop('checked', false);
      tr.removeClass('highlight');
      delete server_list[hostname];
    };

    this.add = function() {
      if (tr.is(':visible')) {
        chbox.prop('checked', true);
        tr.addClass('highlight');
        server_list[hostname] = label.data();
      }
    };

    return this;
  }


  /*
   * **** Are we on server-list page? ****
   */
  this.is_displayed = function() {
    return $('#my_server_list_tbody').length;
  };


  /*
   * **** UPDATE ****
   */
  this.update = function(hostname, status_display, define_changed) {
    // Called from vm_label_update()
    if (server_list.hasOwnProperty(hostname)) {
      server_list[hostname].status_display = status_display;
      if (typeof(define_changed) !== 'undefined') {
        server_list[hostname].define_changed = define_changed;
      }
      toggle_vm_control();
    }
  };


  /*
   * **** START ****
   */
  this.reset_server_list();
  table_init();
  elements.vms_search.focus();


  /*
   * **** ALL ****
   */
  elements.chbox_all.click(function(e) {
    var chbox = $(this);

    if (chbox.prop('checked')) {
      elements.chbox_vms.each(function() {
        server($(this)).add();
      });
    } else {
      elements.chbox_vms.each(function() {
        server($(this)).del();
      });
    }

    toggle_vm_control();

    return true;
  });


  /*
   * **** VMS ****
   */
  elements.chbox_vms.click(function(e) {
    var chbox = $(this);

    if (chbox.prop('checked')) {
      server(chbox).add();
    } else {
      elements.chbox_all.prop('checked', false);
      server(chbox).del();
    }

    toggle_vm_control();

    return true;
  });


  /*
   * **** VM START ****
   */
  elements.vms_start.click(function(e) {
    if (!check_btn(elements.vms_start)) { return false; }

    vms_start();

    return false;
  });

  /*
   * **** VM STOP ****
   */
  elements.vms_stop.click(function(e) {
    if (!check_btn(elements.vms_stop)) { return false; }

    vm_modal(elements.vms_control_modal, elements.vms_stop,
      function() { return vms_stop(false); },
      function() { return vms_stop(true); }
    );

    return false;
  });

  /*
   * **** VM REBOOT ****
   */
  elements.vms_reboot.click(function(e) {
    if (!check_btn(elements.vms_reboot)) { return false; }

    vm_modal(elements.vms_control_modal, elements.vms_reboot,
      function() { return vms_reboot(false); },
      function() { return vms_reboot(true); }
    );

    return false;
  });

  if (admin) {

    /*
     * **** VM UPDATE ****
     */
    elements.vms_update.click(function(e) {
      if (!check_btn(elements.vms_update)) { return false; }

      vms_update();

      return false;
    });

    /*
     * **** VM DEPLOY ****
     */
    elements.vms_deploy.click(function(e) {
      if (!check_btn(elements.vms_deploy)) { return false; }

      vms_deploy();

      return false;
    });

    /*
     * **** VM DELETE ****
     */
    elements.vms_delete.click(function(e) {
      if (!check_btn(elements.vms_delete)) { return false; }

      confirm2(elements.vms_delete.data('confirm'), vms_delete);

      return false;
    });

    /*
     * **** VM DESTROY ****
     */
    elements.vms_destroy.click(function(e) {
      if (!check_btn(elements.vms_destroy)) { return false; }

      vm_modal(elements.vms_control_modal, elements.vms_destroy,
        function() {
          var yes = elements.vms_control_modal.find('a.vm_modal_yes');
          var yes_force = elements.vms_control_modal.find('a.vm_modal_yes_force');
          confirm2(
            elements.vms_destroy.data('modal_confirm_text'),
            function() { yes.hide(); yes_force.fadeIn(); },
            function() { yes.show(); yes_force.hide(); }
          );
          return false;
        },
        function() {
          elements.vms_control_modal.modal('hide');
          return vms_destroy();
        }
      );

      return false;
    });

    /*
     * **** VM FREEZE ****
     */
    elements.vms_freeze.click(function(e) {
      if (!check_btn(elements.vms_freeze)) { return false; }

      vm_modal(elements.vms_control_modal, elements.vms_freeze,
        function() { return vms_freeze(true, false); },
        function() { return vms_freeze(true, true); }
      );

      return false;
    });

    /*
     * **** VM UNFREEZE ****
     */
    elements.vms_unfreeze.click(function(e) {
      if (!check_btn(elements.vms_unfreeze)) { return false; }

      vms_freeze(false, false);

      return false;
    });

  } // is admin

  elements.vms_export.click(function(e) {
    var btn = $(this);

    if (!check_btn(btn)) { return false; }

    var url = btn.data('source') + '?';

    _.each(server_list, function(data, hostname, i) {
      url += '&hostname=' + hostname;
    });

    elements.vms_iframe_download.attr('src', url);

    return false;
  });


  /*
   * **** VM SEARCH ****
   */
  elements.vms_search.keyup(function(e) {
    var val = elements.vms_search.val();

    if (val.length > 0) {
      var pattern = new RegExp(val, 'i');
      elements.tbody_tr.each(function(i, e) {
        var tr = $(e);
        var alias = tr.find('span.vm_alias').text();
        var hostname = tr.find('span.vm_hostname:first').text();
        var state = tr.find('span.label').text();
        if (pattern.test(alias) || pattern.test(hostname) || pattern.test(state)) {
          if (tr.hasClass('visible-by-tag')) {
            tr.show().removeClass('hidden-by-search');
          } else {
            tr.removeClass('hidden-by-search');
          }
        } else {
          tr.hide().addClass('hidden-by-search');
        }
      });
    } else {
      elements.tbody_tr.each(function(i, e) {
        var tr = $(e);
        if (tr.hasClass('visible-by-tag')) {
          tr.show().removeClass('hidden-by-search');
        } else {
          tr.removeClass('hidden-by-search');
        }
      });
    }
  });

} // ServerList()
