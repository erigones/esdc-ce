/* jshint -W030 */

var VM_CONTROL_BTN_TIMEOUT = null;

// Refresh server details page if needed
function vm_refresh_page(hostname) {
  if (!$(jq('vm_header_' + hostname)).length) {
    return false;
  }

  update_content(CURRENT_URL, false);
  return true;
}


/************ TASK CONTROL ************/
// update current tasks UI element
function vm_tasks_update(hostname) {
  var vm_header = $(jq('vm_header_' + hostname));
  var vm_snaps = $(jq('vm_header_snapshots_' + hostname));
  var vm_bkps = $(jq('vm_header_backups_' + hostname));

  // If there is no  header then we are not on the right server page
  if (! (vm_header.length || vm_snaps.length || vm_bkps.length)) {
    return;
  }

  var tasks = VM[hostname]['tasks'] || null;

  vm_header.removeClass('loading-gif-header');
  vm_snaps.removeClass('loading-gif-header');
  vm_bkps.removeClass('loading-gif-header');

  if (tasks && (!$.isEmptyObject(tasks))) {
    $.each(tasks, function(task_id, task) {
      switch (task['view']) {
        case 'vm_status':
        case 'vm_manage':
          vm_header.addClass('loading-gif-header');
          break;
        case 'vm_snapshot':
        case 'vm_snapshot_list':
          vm_snaps.addClass('loading-gif-header');
          break;
        case 'vm_backup':
          vm_bkps.addClass('loading-gif-header');
          break;
      }
    });
  }
}

// update vm tasks from callbacks
function vm_tasks(hostname, res, view, method) {
  var ret = null;

  try {
    if (view == 'vm_define' || view.substring(0, 3) !== 'vm_' ) {
      return null;
    }

    if (!hostname) {
      console.log('ERROR when updating task list - no hostname');
      return null;
    }

    if (typeof(VM) === 'undefined') {
      console.log('ERROR when updating task list - no VM');
      return null;
    }

    if (res.status == 'PENDING' || res.status == 'STARTED') {
      ret = {'view': view, 'method': method};
      VM[hostname]['tasks'][res.task_id] = ret;
    } else {
      ret = VM[hostname]['tasks'][res.task_id];
      delete VM[hostname]['tasks'][res.task_id];
    }
    console.log('VM tasks', VM);
  } catch(err) {
    console.log('VM tasks', err);
  }

  vm_tasks_update(hostname);

  return ret;
}

/************ UI CONTROL ************/

// Add links to VM controls
function vm_control_links(hostname, controls) {
  if (typeof(controls) === 'undefined') {
    var _hostname = _jq(hostname);
    controls = $('.vm_control_'+_hostname + ' a:not(.nocontrol)' + ', .vm_control_admin_'+_hostname + ' a:not(.nocontrol)');
  }
  controls.each(function() {
    var btn = $(this);
    if (btn.hasClass('no-ajax')) {
      btn.click(function() {
        vm_control(hostname, btn);
        return false;
      });
    }
  });
}

// Add links to IP address reverse names
function vm_ptr_links(hostname, niclist) {
  if (typeof(niclist) === 'undefined') {
    niclist = $(jq('vm_nic_' + hostname));
  }
  niclist.find('a.vm_nic_ptr').each(function() {
    var btn = $(this);
    btn.click(function() {
      vm_ptr_change(hostname, btn);
      return false;
    });
  });
}

// Add links to changeable server settings
function vm_settings_links(hostname) {
  $('a.vm_settings').click(function() {
    vm_settings_modal(hostname, $(this), '#vm_settings_modal');
    return false;
  });
  $('a.vm_nic_settings').click(function() {
    vm_settings_modal(hostname, $(this), '#vm_nic_settings_modal');
    return false;
  });
  $('a.vm_disk_settings').click(function() {
    vm_settings_modal(hostname, $(this), '#vm_disk_settings_modal');
    return false;
  });
}

// Return current status or null
function vm_status_display(hostname) {
  var _hostname = _jq(hostname); // escaping dots in hostname

  var label = $('#vm_label_' + _hostname);
  if (label.length) {
    return label.data('status_display');
  }

  var badge = $('#vm_badge_' + _hostname);
  if (badge.length) {
    return badge.data('status_display');
  }

  return null;
}

// Make current status notready
function vm_status_display_notready(hostname) {
  var state = vm_status_display(hostname);

  if (state && (state == 'running' || state == 'stopped' || state == 'notcreated' || state == 'frozen')) {
    return state + '-';
  }

  return 'notready';
}

function vm_flags_update(hostname, data) {
  var flags = $(jq('vm_flags_' + hostname));

  if (!flags.length) {
    return;
  }

  if (data.locked !== undefined) {
    if (data.locked) {
      flags.addClass('icon-lock');
    } else {
      flags.removeClass('icon-lock');
    }
  }
}

// Update VM label according to status
function vm_label_update(hostname, state, apiview) {
  var label = $(jq('vm_label_' + hostname)); // escaping dots in hostname
  if (!label.length) {
    return;
  }

  if (typeof(apiview) === 'undefined') {
    apiview = {};
  }

  var state_text;

  if (state == 'unknown') {
    state_text = label.text(); // Keep last known state text
  } else {
    state_text = gettext(state);
  }

  label.data('status_display', state);
  label.fadeOut('fast', function() {
    $(this).removeClass().addClass('label status_' + state).text(state_text).fadeIn();
  });

  if (typeof(apiview.define_changed) !== 'undefined') {
    label.data('define_changed', apiview.define_changed);
  }

  if (typeof(apiview.locked) !== 'undefined') {
    label.data('locked', apiview.locked);
    vm_flags_update(hostname, apiview);
  }

  // Hide modal if shown
  if ((typeof(MODAL) !== 'undefined') && MODAL) {
    MODAL.modal('hide');
    MODAL = null;
  }

  // Also update the server-list on server_list view
  if ((typeof(VMS) !== 'undefined') && VMS && VMS.is_displayed()) {
    VMS.update(hostname, state, apiview.define_changed);
  }
}

// Update VM badge according to status
function vm_badge_update(hostname, state) {
  var badge = $(jq('vm_badge_' + hostname)); // escaping dots in hostname
  if (!badge.length) {
    return;
  }

  badge.data('status_display', state);
  badge.fadeOut('fast', function() {
    $(this).removeClass().addClass('icon-hdd ' + state).fadeIn();
  });
}

// Update node information on VM details and VM list page
function vm_node_update(hostname, result) {
  var vm_node = $(jq('vm_node_' + hostname));

  if (!vm_node.length) {
    return;
  }

  if (result.node) {
    if ('color' in result.node) {
      vm_node.find('.vm_node_color').css('color', result.node.color);
    }

    if ('hostname' in result.node) {
      vm_node.find('.vm_node_hostname').text(result.node.hostname);

      // If node info in VM list was updated then we have to refresh the data table
      if ((typeof(VMS) !== 'undefined') && VMS && VMS.is_displayed()) {
        VMS.refresh_vm_node(hostname);
      }
    }
  }
}

// Update VM define data
function vm_define_update(hostname, result, kwargs) {
  if (kwargs && 'node' in kwargs.data) {
    vm_node_update(hostname, result);
  }
}

// Update VM replica sync status
function vm_replica_status_update(hostname, result) {
  var rep_status = $(jq('vm_replica_status_' + hostname));

  if (!rep_status.length) {
    return; // Not on server details page
  }

  if (typeof(result.last_sync) === 'undefined') {
    return; // Missing last_sync -> nothing to do
  }

  function set_last_sync() {
    var last_sync;
    if (result.last_sync) {
      last_sync = moment(result.last_sync).tz(CURRENT_TZ).strftime(LONG_DATETIME_FORMAT);
      rep_status.find('.vm_replica_last_sync').html(last_sync);
    }
  }

  if (result._event_ == 'vm_replica_synced') {
    // VM replica sync event -> update only last_sync datetime
    set_last_sync();
    return;
  }

  if (result.enabled === null) {
    // Replica was deleted
    rep_status.hide();
  } else if (result.enabled === false) {
    rep_status.find('.vm_replica_sync_status').removeClass('icon-enabled').addClass('icon-disabled');
    set_last_sync();
    rep_status.show();
  } else if (result.enabled === true) {
    rep_status.find('.vm_replica_sync_status').removeClass('icon-disabled').addClass('icon-enabled');
    set_last_sync();
    rep_status.show();
  }
}

function vm_replica_control_update(hostname, result) {
  var btn = $(jq('vm_replication__' + hostname));

  if (!btn.length) {
    return;
  }

  if (result.enabled === null) {
    btn.removeClass('obj_edit').addClass('obj_add');
    btn.data('form', {});
  } else {
    btn.removeClass('obj_add').addClass('obj_edit');
    btn.data('form', result);
  }
}

// Update replication modal with error or hide it (used only by failover or reinit)
function vm_replica_modal_update(hostname, errors) {
  var mod = $('#vm_replica_modal');

  if (mod.length && (mod.data('vm') == hostname)) {
    if (errors) {
      mod.find('div.modal_error').show().find('span').html('').text(errors[0]);
    } else {
      mod.modal('hide');
    }
  }
}

// Enable or disable rollback button in rollback modal (plus control warning)
function vm_snapshot_rollback_modal_update(hostname, allow) {
  var mod = $('#vm_snapshot_rollback_modal');
  if (!mod.length) {
    return;
  }

  var ale = mod.find('div.vm_modal_alert');
  var yes_force = mod.find('a.vm_modal_yes_force');

  if (allow) {
    ale.addClass('hide');
    yes_force.removeClass('disabled');
    yes_force.data('stay_disabled', false);
  } else {
    ale.removeClass('hide');
    yes_force.addClass('disabled');
    yes_force.data('stay_disabled', true);
  }
}

function vm_control_toggle(elem, show) {
  if (!elem.length) {
    return;
  }
  if (show === true) {
    elem.show();
  } else if (show === false) {
    elem.hide();
  }
}

function vm_links_toggle(elem, enabled) {
  if (!elem.length) {
    return;
  }

  if (enabled === true) {
    elem.not('.stay_disabled').removeClass('disabled');
    if (!is_touch_device()) {
      elem.tooltip('enable');
    }
  } else if (enabled === false) {
    elem.addClass('disabled');
    if (!is_touch_device()) {
      elem.tooltip('disable');
    }
  }
}

function vm_lock_toggle(locked) {
  var elem_locked = $('span.vm_locked');
  var elem_unlocked;

  if (elem_locked.length) {
    elem_unlocked = $('a.vm_unlocked');
    if (locked === true) {
      elem_locked.show();
      $('a.vm_lock_disable').addClass('disabled', 'stay_disabled');
    } else if (locked === false) {
      elem_locked.hide();
    }
  }
}

function vm_forms_toggle(enabled, mod) {
  var input, select;

  if (typeof(mod) === 'undefined') {
    input = $('.disable_created');
    select = $('select.disable_created2');
  } else {
    input = mod.find('.disable_created');
    select = mod.find('select.disable_created2');
  }

  if (enabled === true) {
    input.removeProp('disabled').removeClass('uneditable-input').addClass('input-transparent');
    select.removeProp('disabled');
  } else if (enabled === false) {
    input.prop('disabled', true).addClass('uneditable-input').removeClass('input-transparent');
    select.prop('disabled', true);
  }
}

function vm_disk_settings_modal_update(hostname, force) {
  var mod = $('#vm_disk_settings_modal');

  if (!mod.length) {
    return;
  }

  if (force) {
    $('#vm_settings_modal a.vm_modal_delete').removeClass('disabled');
  } else {
    $('#vm_settings_modal a.vm_modal_delete').addClass('disabled');
  }

  mod.find('a.vm_modal_delete').data('force', force);
  mod.find('#id_opt-disk-size').data('force', force);
}

// Call object toggler
function vm_object_toggle(obj, hostname, enabled) {
  if (obj) {
    obj.control_toggle(hostname, enabled);
  }
}

// Will disable/enable snapshot multi delete
function vm_snapshots_toggle(hostname, enabled) {
  vm_object_toggle(VM_SNAPSHOTS, hostname, enabled);
}

// Enable or disable VM controls
function vm_control_update(hostname, state, apiview) {
  var _hostname = _jq(hostname);
  var control = $('.vm_control_' + _hostname);
  if (!control.length) {
    return;
  }

  if (typeof(apiview) === 'undefined') {
    apiview = {};
  }

  var vm_locked = get(apiview, 'locked', control.data('vm_locked'));
  var disabled = 'disabled';

  if (vm_locked) {
    disabled = false;
  } else {
    control.data('vm_locked', vm_locked);
  }

  var vm_snapshots = $('#vm_snapshots_' + _hostname + ' a, #vm_snapshot_define_' + _hostname + ' a');
  var vm_settings = $('a.vm_settings, a.vm_disk_settings, a.vm_nic_settings, a.vm_nic_ptr');
  var vm_msg_not_installed = $('#vm_msg_not_installed');

  var vm_start = $('#vm_start__' + _hostname);
  var vm_stop = $('#vm_stop__' + _hostname);
  var vm_reboot = $('#vm_reboot__' + _hostname);
  var vm_startcd = $('#vm_startcd__' + _hostname);
  var vm_reset = $('#vm_reset__' + _hostname);
  var vm_console = $('#vm_console__' + _hostname);
  var vm_update;
  var vm_undo;
  var vm_deploy;
  var vm_destroy;
  var vm_delete;
  var vm_freeze;
  var vm_unfreeze;
  var vm_migrate;
  var vm_replication;

  var control_admin = $('.vm_control_admin_' + _hostname);
  if (control_admin.length) {
    vm_update = $('#vm_update__' + _hostname);
    vm_undo = $('#vm_undo__' + _hostname);
    vm_deploy = $('#vm_deploy__' + _hostname);
    vm_destroy = $('#vm_destroy__' + _hostname);
    vm_delete = $('#vm_delete__' + _hostname);
    vm_freeze = $('#vm_freeze__' + _hostname);
    vm_unfreeze = $('#vm_unfreeze__' + _hostname);
    vm_migrate = $('#vm_migrate__' + _hostname);
    vm_replication = $('#vm_replication__' + _hostname);
  }

  function toggle_vm_update() {
    if (apiview.define_changed === true) {
      vm_update.removeClass('disabled').addClass('define_changed');
      vm_undo.removeClass('disabled').addClass('define_changed_undo');
      vm_start.addClass('define_changed');
    } else { // admin can run update even when nothing has changed
      vm_update.removeClass('disabled');
    }
  }

  function vm_control_disable() {
    if (control_admin.length) {
      vm_update.addClass('disabled').removeClass('define_changed').hide();
      vm_undo.addClass('disabled').removeClass('define_changed_undo').hide();
      vm_deploy.addClass('disabled').hide();
      vm_destroy.addClass('disabled').hide();
      vm_delete.addClass('disabled').hide();
      vm_freeze.addClass('disabled').hide(); vm_freeze.data('modal_force_only', false);
      vm_unfreeze.addClass('disabled').hide();
      vm_migrate.addClass('disabled').hide();
      vm_replication.addClass('disabled').hide();
    }
    vm_start.addClass('disabled').removeClass('define_changed');
    vm_stop.addClass('disabled'); vm_stop.data('modal_force_only', false);
    vm_reboot.addClass('disabled');
    vm_startcd.addClass('disabled');
    vm_reset.addClass('disabled');
    vm_console.addClass('disabled');
    vm_snapshot_rollback_modal_update(hostname, false);
    vm_disk_settings_modal_update(hostname, false);
    vm_links_toggle(vm_settings, false);
    vm_links_toggle(vm_snapshots, false); vm_snapshots_toggle(hostname, false);
    vm_control_toggle(vm_msg_not_installed, false);
    vm_forms_toggle(false);
  }

  switch (state) {

    case 'running':
      vm_control_disable();
      if (control_admin.length) {
        vm_update.show(); vm_undo.show(); toggle_vm_update();
        vm_destroy.show();
        vm_freeze.show().removeClass('disabled');
        vm_migrate.show().removeClass(disabled);
        vm_replication.show().removeClass('disabled');
        control_admin.slideDown();
      }
      vm_stop.removeClass('disabled');
      vm_reboot.removeClass('disabled');
      vm_console.removeClass('disabled');
      vm_links_toggle(vm_settings, true);
      vm_links_toggle(vm_snapshots, true); vm_snapshots_toggle(hostname, true);
      vm_control_toggle(vm_msg_not_installed, true);
      control.slideDown();
      break;

    case 'stopped':
      vm_control_disable();
      if (control_admin.length) {
        vm_update.show(); vm_undo.show(); toggle_vm_update();
        vm_destroy.show().removeClass(disabled);
        vm_freeze.show().removeClass('disabled');
        vm_migrate.show().removeClass(disabled);
        vm_replication.show().removeClass('disabled');
        control_admin.slideDown();
      }
      vm_start.removeClass('disabled');
      vm_startcd.removeClass('disabled');
      vm_reset.removeClass(disabled);
      vm_snapshot_rollback_modal_update(hostname, !vm_locked);
      vm_links_toggle(vm_settings, true);
      vm_links_toggle(vm_snapshots, true); vm_snapshots_toggle(hostname, true);
      vm_control_toggle(vm_msg_not_installed, true);
      control.slideDown();
      $('#vm_msg_frozen').addClass('hide');
      break;

    case 'stopping':
      vm_control_disable();
      if (control_admin.length) {
        vm_update.show();
        vm_undo.show();
        vm_destroy.show();
        vm_freeze.show().removeClass('disabled'); vm_freeze.data('modal_force_only', true);
        vm_migrate.show();
        vm_replication.show();
        control_admin.slideDown();
      }
      vm_stop.removeClass('disabled'); vm_stop.data('modal_force_only', true);
      vm_console.removeClass('disabled');
      vm_links_toggle(vm_settings, true);
      vm_links_toggle(vm_snapshots, true); vm_snapshots_toggle(hostname, true);
      vm_control_toggle(vm_msg_not_installed, true);
      control.slideDown();
      break;

    case 'notcreated':
      vm_control_disable();
      if (control_admin.length) {
        vm_deploy.show().removeClass('disabled');
        vm_delete.show().removeClass('disabled');
        control_admin.slideDown();
      }
      vm_disk_settings_modal_update(hostname, true);
      vm_links_toggle(vm_settings, true);
      vm_forms_toggle(true);
      control.slideDown();
      break;

    case 'notready':
    case 'stopped-':
    case 'running-':
    case 'frozen-':
    case 'notcreated-':
      vm_control_disable();
      if (control_admin.length) {
        vm_update.show();
        vm_undo.show();
        vm_destroy.show();
        vm_freeze.show();
        vm_migrate.show();
        vm_replication.show();
        control_admin.slideDown();
      }
      control.slideDown();
      break;

    case 'pending':
      vm_control_disable();
      if (control_admin.length) {
        control_admin.not('.vm_control_nohide').slideUp();
      }
      control.not('.vm_control_nohide').slideUp();
      vm_control_toggle(vm_msg_not_installed, true);
      break;

    case 'creating':
    case 'deploying':
    case 'unknown':
    case 'error':
      vm_control_disable();
      if (control_admin.length) {
        control_admin.not('.vm_control_nohide').slideUp();
      }
      control.not('.vm_control_nohide').slideUp();
      break;

    case 'frozen':
      vm_control_disable();
      if (control_admin.length) {
        vm_update.show();
        vm_undo.show();
        vm_destroy.show();
        vm_unfreeze.show().removeClass('disabled');
        vm_migrate.show();
        vm_replication.show().removeClass('disabled');
        control_admin.slideDown();
        control.slideDown();
      } else {
        control.not('.vm_control_nohide').slideUp();
      }
      $('#vm_msg_frozen').removeClass('hide');
      break;
  }

  vm_lock_toggle(vm_locked);
}

// Display PTR change modal and perform PTR update
function vm_ptr_change(hostname, btn) {
  if (btn.hasClass('disabled')) {
    return false;
  }
  var ptr_content = btn.parent().find('.ptr-content');
  var ipaddr = btn.data('ipaddr');
  var mod = $('#vm_ptr_modal');
  var text = mod.find('div.vm_modal_text');
  var text_default = text.html();
  var form = mod.find('form');
  var form_default = form.html();
  var ptr = form.find('#id_ptr-content');
  var yes = mod.find('a.vm_modal_yes');
  disable_form_submit(form);

  text.html(text_default.replace('__ipaddr__', ipaddr));
  ptr.val(ptr_content.html());

  var handler = function() {
    ajax('POST', btn.data('source'), ATIMEOUT, function(data, textStatus, jqXHR) {
      if (jqXHR.status == 201) {
        mod.modal('hide');
        ptr_content.html(form.find('#id_ptr-content').val());
      } else if (jqXHR.status == 204) {
        mod.modal('hide');
      } else {
        form.html(data);
      }
    }, form.serialize());
  };

  mod.one('hide', function() {
    yes.off('click');
  });
  mod.one('hidden', function() {
    text.html(text_default);
    if (form.length) {
      form.html(form_default);
      form[0].reset();
    }
  });
  yes.on('click', handler);

  activate_modal_ux(mod, form);
  mod.modal('show');
}

// Settings (server, nic, disk) modal
function vm_settings_modal(hostname, btn, mod_selector) {
  if (btn.hasClass('disabled')) {
    return false;
  }

  var mod = $(mod_selector);
  var add = btn.hasClass('vm_add');
  var form = mod.find('form');
  var form_default = form.html();
  var btn_update = mod.find('a.vm_modal_update');
  var btn_delete = mod.find('a.vm_modal_delete');
  var btn_create = mod.find('a.vm_modal_create');
  var btn_more = mod.find('a.vm_modal_more');
  var title_edit = mod.find('span.title_edit');
  var title_add = mod.find('span.title_add');
  var select = mod.find('select.input-select2');
  disable_form_submit(form);

  function fix_form(init) {
    if (mod_selector == '#vm_settings_modal') {
      var tags_select = $('#id_opt-tags');
      tags_select.select2({tags: ServerListTags.tags(), dropdownCssClass: tags_select.attr('class'), tokenSeparators: [',', ' ']});

      mdata_display($('#id_opt-mdata'));
      mbytes_handler($('#id_opt-ram'));
      mon_templates_enable($('#id_opt-monitoring_templates'));
      mon_hostgroups_enable($('#id_opt-monitoring_hostgroups'));

      if (init && add) {  // switching template affects VM form fields only when adding new VM
        mod.on('change', '#id_opt-template', function() {
          var tmpdata = $(this).find('option:selected').data('object');

          update_form_fields(form, tmpdata, 'opt');
        });
      }

    } else if (mod_selector == '#vm_nic_settings_modal') {
      var nic_ip = $('#id_opt-nic-ip');
      var ip_placeholder = nic_ip.attr('placeholder');
      var netdata = $('#id_opt-nic-net').find('option:selected').data('object');
      var nic_config = {
        '#id_opt-nic-monitoring': [false, $('#id_opt-nic-monitoring').prop('checked'), false],
        '#id_opt-nic-dns': [false, $('#id_opt-nic-dns').prop('checked'), false],
      };

      var set_dhcp_passtgrough = function(value, key) {
        $(key).prop('checked', nic_config[key][2]);
      };

      var reset_default = function(value, key) {
        if (!nic_config[key][0]) {  // Reset only if not changed manually
          $(key).prop('checked', nic_config[key][1]);
        }
      };

      var mark_change = function() {
        nic_config['#' + $(this).attr('id')][0] = true;
      };

      _.each(nic_config, function(value, key){
        mod.on('change', key, mark_change);
      });

      if (netdata && netdata.dhcp_passthrough) {
        nic_ip.attr('placeholder', '');
      }

      mod.on('change', '#id_opt-nic-net', function() {
        var netdata = $(this).find('option:selected').data('object');

        nic_ip.val('').attr('placeholder', ip_placeholder);
         _.each(nic_config, reset_default);

        if (netdata) {
          if (netdata.dhcp_passthrough) {
            nic_ip.attr('placeholder', '');
            _.each(nic_config, set_dhcp_passtgrough);
          }
        }
      });

    } else if (mod_selector == '#vm_disk_settings_modal') {
      var disk_id = $('#id_opt-disk-disk_id').val();
      var is_kvm = mod.data('is_kvm');

      if (disk_id > 1) {
        $('#id_opt-disk-image').parent().parent().parent().hide();

        if (is_kvm) {
          $('#id_opt-disk-boot').parent().parent().parent().hide();
          $('#id_opt-disk-zpool').parent().find('span.note').hide();
        } else {
          $('#id_opt-disk-size').parent().parent().parent().hide();
          $('#id_opt-disk-zpool').parent().parent().parent().hide();
        }
      } else { // disk_id == 1

        if (init) {
          mod.on('change', '#id_opt-disk-image', function() {
            var size = $('#id_opt-disk-size');
            var imgdata = $(this).find('option:selected').data('object');
            if (imgdata && 'size' in imgdata) {
              size.attr('placeholder', imgdata.size);
              if (!size.val()) {
                size.val(imgdata.size);
              }
            }
          });
        }

        if (is_kvm) {
          var zpool_change = function(select) {
            if (select.val() == $('#id_opt-zpool').val()) {
              select.parent().find('span.note').css('font-weight', 'normal');
            } else {
              select.parent().find('span.note').css('font-weight', 'bold');
            }
          };

          mod.on('change', '#id_opt-disk-zpool', function() {
            zpool_change($(this));
          });

          zpool_change($('#id_opt-disk-zpool'));
        }
      }

      mbytes_handler($('#id_opt-disk-size'));

      mod.on('change', '#id_opt-disk-size', function() {
        var size = $(this);
        //$('#id_opt-disk-refreservation').val(size.val());  // refreservation disabled

        /* jshint -W041 */
        if ((size.data('force') == false) && (size.val() != size.attr('placeholder'))) {
          btn_update.data('force', false);
        } else {
          btn_update.data('force', 'true');
        }
        /* jshint +W041 */
      });
    }

    if (!init) {
      // Focus on first error
      scroll_to_modal_error(mod);
    }
  } // fix_form


  var morehandler = function(e) {
    var advanced = mod.find('div.advanced');

    if (e === true) {
      advanced.show();
      btn_more.addClass('active');
    } else if (e === false) {
      advanced.hide();
      btn_more.removeClass('active');
    } else {
      advanced.toggle();
      btn_more.button('toggle');
    }

    if (btn_more.hasClass('active')) {
      advanced.get(0).scrollIntoView();
    }

  };


  var handler = function(e) {
    var action_btn = $(this);
    if (action_btn.hasClass('disabled')) {
      return false;
    }

    var post_data_fun = function() {
      // glue together JSON for mdata
      mdata_handler(mod.find('#id_opt-mdata'));

      form.find(':input').removeProp('disabled');

      ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, xhr) {
        if (xhr.status == 278) {
          mod.modal('hide');
          ajax_move(null, xhr.getResponseHeader('Location'));

        } else if (xhr.status == 204) {
          mod.modal('hide');

        } else {
          form.html(data);
          select = $(select.selector);
          vm_forms_toggle(add, mod);
          select.select2({dropdownCssClass: select.attr('class')});

          if (mod.find('div.advanced div.input.error').length || btn_more.hasClass('active')) {
            morehandler(true);
          }

          fix_form(false);

        }
      }, form.serialize() + '&siosid=' + get_siosid() + '&action=' + e.data.action);
    };

    /* jshint -W041 */
    if (action_btn.data('force') == false) {
      confirm2(action_btn.data('confirm'), post_data_fun);
    } else {
      post_data_fun();
    }
    /* jshint +W041 */
  };


  if (add) {
    title_add.show();
    title_edit.hide();
    btn_update.length && btn_update.hide();
    btn_delete.length && btn_delete.hide();
    btn_create.length && btn_create.show();
    vm_forms_toggle(true, mod);
  } else {
    title_add.hide();
    title_edit.show();
    btn_update.length && btn_update.show();
    btn_delete.length && btn_delete.show();
    btn_create.length && btn_create.hide();

    var form_data = btn.data('form') || null;

    if (form_data) {
      var prefix = btn.data('prefix');

      if (prefix) {
        prefix += '-';
      } else {
        prefix = '';
      }

      _.each(form_data, function(value, item, i) {
        var field = form.find('#id_' + prefix + item);

        if (!field.length) { return; }

        if (value === true || value === false) {
          field.prop('checked', value);
        } else {
          if (value === null) { value = ''; }
          field.val(value);
          field.attr('placeholder', value);
        }
      });
    }
  }

  mod.one('hide', function() {
    btn_update.length && btn_update.off('click');
    btn_delete.length && btn_delete.off('click');
    btn_create.length && btn_create.off('click');
    if (btn_more.length) { btn_more.off('click'); morehandler(false); }

    select.select2('destroy');

    if (mod_selector == '#vm_settings_modal') {
      $('#id_opt-tags').select2('destroy');
      mod.off('change', '#id_opt-template');

    } else if (mod_selector == '#vm_disk_settings_modal') {
      mod.off('change', '#id_opt-disk-image');
      mod.off('change', '#id_opt-disk-size');
    }

  });

  mod.one('hidden', function() {
    if (form.length) {
      form.html(form_default);
      form[0].reset();
    }
  });

  btn_update.length && btn_update.on('click', {action: 'update'}, handler);
  btn_delete.length && btn_delete.on('click', {action: 'delete'}, handler);
  btn_create.length && btn_create.on('click', {action: 'create'}, handler);
  btn_more.length && btn_more.on('click', morehandler);

  select.select2({dropdownCssClass: select.attr('class')});

  fix_form(true);

  activate_modal_ux(mod, form);
  mod.modal('show');
}

// Revert server definition
function vm_undo(hostname) {
  var form = $('#undo_settings_form');
  var post_data = form.serialize() + '&action=update';

  ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, xhr) {
    if (xhr.status == 278) {
      ajax_move(null, xhr.getResponseHeader('Location'));
    }
  }, post_data);
}

// Toggle vm_migrate modal window
function vm_migrate_update(hostname, started, errors) {
  var mod = $('#vm_migrate_modal');

  if (mod.length && (mod.data('vm') == hostname)) {
    if (started) {
      mod.modal('hide');
    } else {
      if (errors) {
        mod.find('#vm_migrate_modal_error').show().find('span').html('').text(errors[0]);
      }
    }
  }
}

// Helper for getting ISO image value
function iso_image_value(mod) {
  var cdimage_chooser = $('#id_iso-image');

  if (cdimage_chooser.length) {
    var cdimage2_chooser = $('#id_iso2-image');
    var cdimage_once = $('#id_iso-image-once').prop('checked');
    var iso = cdimage_chooser.val();
    var ret = [iso, cdimage_once, null];

    // Save last choice if not checked
    if (!cdimage_once && iso) {
      mod.data('last_cdimage', iso);
    } else {
      mod.data('last_cdimage', '');
    }

    if (cdimage2_chooser.length) {
      ret[2] = cdimage2_chooser.val();
    }

    return ret;
  }
  return [false, undefined, undefined];
}

// Restore last cd image choice (stored if once was unchecked)
function iso_image_value_restore(mod) {
  if (mod.data('last_cdimage')) {
    $('#id_iso-image').val(mod.data('last_cdimage'));
    $('#id_iso-image-once').prop('checked', false);
  }
}

// VM control commands
function vm_control(hostname, btn) {
  if (btn.hasClass('disabled') || btn.hasClass('clicked')) {
    return false;
  }

  var action = btn.attr('id').split('_');
  var mod, form;
  btn.addClass('clicked');
  VM_CONTROL_BTN_TIMEOUT = setTimeout(function() { btn.removeClass('clicked'); }, 500);

  switch(action[1]) {
    case 'start':
      var btn_vm_update = $(jq('vm_update__' + hostname));

      if (btn_vm_update.length && btn_vm_update.hasClass('define_changed')) {
        return vm_modal($('#vm_control_modal'), btn_vm_update,
          function() { return vm_start(hostname, null, true); },
          function() { return vm_start(hostname, null, false); }
        );
      } else {
        return vm_start(hostname, false);
      }
      break;

    case 'stop':
    case 'reboot':
      return vm_modal($('#vm_control_modal'), btn,
        function() {
          return vm_stop_or_reboot(hostname, action[1], false);
        },
        function() {
          return vm_stop_or_reboot(hostname, action[1], true);
        }
      );

    case 'console':
      ajax_move(btn[0]);
      return false;

    case 'startcd':
      if (btn.data('rescuecd')) {
        return vm_modal($('#vm_control_modal'), btn, function() {
          return vm_start(hostname, RESCUECD, false);
        });
      } else {
        mod = $('#vm_startcd_modal');
        iso_image_value_restore(mod);
        return vm_modal(mod, btn,
          function() { var iso = iso_image_value(mod); return vm_start(hostname, iso[0], false, iso[1], iso[2]); }
        );
      }
      break;

    case 'snapshot':
      return vm_snapshot_create_modal(hostname, btn);

    case 'backup':
      return vm_backup_create_modal(hostname, btn);

    case 'snapshots':
      vm_snapshots_delete_modal(hostname, btn, vm_destroy_snapshots);
      return false;

    case 'backups':
      vm_snapshots_delete_modal(hostname, btn, vm_destroy_backups);
      return false;

    case 'reset':
      mod = $('#vm_control_modal');
      return vm_modal(mod, btn,
        function() {
          var yes = mod.find('a.vm_modal_yes');
          var yes_force = mod.find('a.vm_modal_yes_force');
          confirm2(
            btn.data('modal_confirm_text'),
            function() { yes.hide(); yes_force.fadeIn(); },
            function() { yes.show(); yes_force.hide(); }
          );
          return false;
        },
        function() {
          mod.modal('hide');
          return vm_recreate(hostname, true);
        }
      );

    case 'installed':
      mod = $('#vm_control_modal');
      form = $('#vm_installed_form');
      return vm_modal(mod, btn, function() {
        return ajax_json('POST', form.data('source'), ATIMEOUT, function(data, textStatus, xhr) {
          if (xhr.status == 278) {
            ajax_move(null, xhr.getResponseHeader('Location'));
          }
        }, form.serialize());
      });

    case 'update':
      return vm_update(hostname);

    case 'undo':
      return vm_undo(hostname);

    case 'deploy':
      return vm_create(hostname);

    case 'delete':
      confirm2(btn.data('confirm'), function() {
        form = $('#vm_settings_form');
        form.find(':input').removeProp('disabled');

        return ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, xhr) {
          if (xhr.status == 278) {
            ajax_move(null, xhr.getResponseHeader('Location'));
          } else {
            notify('error', $(data).find('div.alert-error, span.error').text());
          }
        }, form.serialize() + '&action=delete');
      });
      return false;

    case 'destroy':
      mod = $('#vm_control_modal');
      return vm_modal(mod, btn,
        function() {
          var yes = mod.find('a.vm_modal_yes');
          var yes_force = mod.find('a.vm_modal_yes_force');
          confirm2(
            btn.data('modal_confirm_text'),
            function() { yes.hide(); yes_force.fadeIn(); },
            function() { yes.show(); yes_force.hide(); }
          );
          return false;
        },
        function() {
          mod.modal('hide');
          return vm_delete(hostname);
        }
      );

    case 'freeze':
      return vm_modal($('#vm_control_modal'), btn,
        function() {
          return vm_freeze(hostname, true, false);
        },
        function() {
          return vm_freeze(hostname, true, true);
        }
      );

    case 'unfreeze':
      return vm_freeze(hostname, false, false);

    case 'migrate':
      mod = $('#vm_migrate_modal');
      return vm_modal(mod, btn, function() {
        mod.find('#vm_migrate_modal_error').hide();
        return vm_migrate(hostname, $('#id_migrate-node').val());
      });

    case 'replication':
      new obj_form_modal(btn, '#vm_replica_modal', function(modal, start) {
        var btn_failover = modal.mod.find('#vm_replica_failover');
        var btn_reinit = modal.mod.find('#vm_replica_reinit');
        var form_data = modal.form_data;

        if (start) {
          modal.mod.find('div.modal_error').hide();
          btn_failover.off('click');
          btn_reinit.off('click');

          if (form_data && form_data.last_sync) {
            if (form_data.reinit_required) {
              btn_failover.hide();
              btn_reinit.show().on('click', function() {
                vm_replica_reinit(form_data.hostname, form_data.repname);
              });
            } else {
              btn_reinit.hide();
              btn_failover.show().on('click', function() {
                vm_replica_failover(form_data.hostname, form_data.repname);
              });
            }
          } else {
            btn_failover.hide();
            btn_reinit.hide();
          }
        }
      });
      return false;

    default:
      return false;
  }
}
