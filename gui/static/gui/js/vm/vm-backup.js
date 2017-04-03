/* jshint -W030 */

// Add links to snapshot define list/buttons
function vm_snapshot_define_links(hostname) {
  var define_links = $(jq('vm_snapshot_define_' + hostname + ' a'));

  if (!define_links.length) {
    return;
  }

  define_links.off('click').click(function() {
    vm_snapshot_define_modal(hostname, $(this), '#vm_snapshot_define_modal');
    return false;
  });
}

// Add links to snapshot list
function vm_snapshot_list_links(hostname, snaplist) {
  // backup now button
  vm_control_links(hostname, snaplist.find('tfoot a'));
  // snapshot note links
  snaplist.find('tbody a.vm_snapshot_note').click(function() {
    vm_snapshot_update(hostname, $(this));
    return false;
  });
  // snapshot name links
  snaplist.find('tbody a.vm_snapshot_name').click(function() {
    var btn = $(this);
    if (btn.data('backup')) {
      vm_backup_restore(hostname, btn, vm_destroy_backup, vm_restore_backup);
    } else {
      vm_snapshot_rollback(hostname, btn, vm_destroy_snapshot, vm_rollback_snapshot);
    }
    return false;
  });
  // remove info class
  table_obj_added(snaplist.find('tr.info'))
}

// Update list of snapshots/backups with html from server and add links
function _vm_snapshots_update(hostname, snaplist, state, last_snapname, last_disk_id) {
  if (!snaplist.length) {
    return;
  }

  var url = snaplist.data('source');
  if (!url) {
    return;  // We don't want to update the snapshot list
  }

  var page = snaplist.data('page');
  if (page && page != '1') {
    url += '?page=' + page;
  } else {
    url += '?';
  }

  var order_by = snaplist.data('order_by');
  if (order_by) {
    url += '&order_by=' + order_by;
  }

  var qs = snaplist.data('qs');
  if (qs) {
    url += + '&' + qs;
  }

  if (typeof(last_disk_id) !== 'undefined') {
    url += '&last_snapid=' + last_disk_id + '_' + last_snapname;
  }

  ajax('GET', url, ATIMEOUT, function(data, textStatus, jqXHR) {
    if (VM_SNAPSHOTS.hostname != hostname) {
      return false;
    }

    // Destroy table
    VM_SNAPSHOTS.destroy(); VM_SNAPSHOTS = null;
    // Update DOM
    snaplist.html(data);
    // Enable links & table
    VM_SNAPSHOTS = new _SnapshotList(hostname, snaplist);
    // vm_control_update also updates snapshot list links, so run it after new list is in place
    if (state && hostname) {
      vm_control_update(hostname, state);
    }
    // IF there is a total counter on the page, then update it (nav-menu @ node)
    var count = $(jq('vm_snapshot_count_' + hostname));
    if (count.length) {
      count.text(snaplist.find('#total').text());
    }
  });
}
// Update list of snapshots with html from server and add links
function vm_snapshots_update(hostname, state, last_snapname, last_disk_id) {
  return _vm_snapshots_update(hostname, $(jq('vm_snapshots_' + hostname)), state, last_snapname, last_disk_id);
}
// Update list of backups with html from server and add links
function vm_backups_update(hostname, state, last_snapname, last_disk_id) {
  return _vm_snapshots_update(hostname, $(jq('vm_backups_' + hostname)), state, last_snapname, last_disk_id);
}


// Update snapshot/backup rollback/restore/delete modal with error or hide it
function _vm_snapshot_modal_update(hostname, snaplist, errors) {
  // Check if we are on the right page
  if (!snaplist.length) {
    return;
  }

  // Check if we have a modal
  if (MODAL && MODAL.length && (MODAL.selector.indexOf('vm_snapshot') > -1)) {
    if (errors) {
      MODAL.find('div.modal_error').show().find('span').html('').text(errors[0]);
    } else {
      MODAL.modal('hide');
    }
  }
}
// Update snapshot rollback/restore/delete modal with error or hide it
function vm_snapshot_modal_update(hostname, errors) {
  return _vm_snapshot_modal_update(hostname, $(jq('vm_snapshots_' + hostname) + ', #vm_snapshots_'), errors);
}
// Update backup rollback/restore/delete modal with error or hide it
function vm_backup_modal_update(hostname, errors) {
  return _vm_snapshot_modal_update(hostname, $(jq('vm_backups_' + hostname) + ', #vm_backups_'), errors);
}


// Create snapshot modal
function vm_snapshot_create_modal(hostname, btn) {
  var mod = $('#vm_snapshot_modal');

  function toggle_disk_id() {
    if ($('#id_snap_create-disk_all').prop('checked')) {
      $('#id_snap_create-disk_id').prop('disabled', 'disabled');
    } else {
      $('#id_snap_create-disk_id').removeProp('disabled');
    }

  }

  $('#id_snap_create-disk_all').off('click').click(toggle_disk_id);

  return vm_modal(mod, btn, function(e) {
    if ($(this).hasClass('disabled')) {
      return false;
    }

    var form = mod.find('form');
    $('#id_snap_create-hostname').removeProp('disabled');
    $('#id_snap_create-disk_id').removeProp('disabled');

    return ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, jqXHR) {
      if (jqXHR.status == 201) {
        mod.modal('hide');
        var name = form.find('#id_snap_create-name').val();
        var disk_id = form.find('#id_snap_create-disk_id');
        var fsfreeze = form.find('#id_snap_create-fsfreeze').prop('checked');
        var note = form.find('#id_snap_create-note').val();

        if ($('#id_snap_create-disk_all').prop('checked')) {
          disk_id.find('option').each(function() { vm_create_snapshot(hostname, name, $(this).val(), fsfreeze, note); });
        } else {
          vm_create_snapshot(hostname, name, disk_id.val(), fsfreeze, note);
        }

        return false;

      } else {
        e.data.modal.update_form(data);
        toggle_disk_id();
        $('#id_snap_create-disk_all').off('click').click(toggle_disk_id);
      }
    }, form.serialize());
  });
}

// Create backup modal
function vm_backup_create_modal(hostname, btn) {
  var mod = $('#vm_backup_modal');

  return vm_modal(mod, btn, function(e) {
    if ($(this).hasClass('disabled')) {
      return false;
    }

    var form = mod.find('form');
    $('#id_snap_create-hostname').removeProp('disabled');

    return ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, jqXHR) {
      if (jqXHR.status == 201) {
        mod.modal('hide');
        var define_diskid = form.find('#id_snap_create-define').val().split('@');
        var note = form.find('#id_snap_create-note').val();
        vm_create_backup(hostname, define_diskid[0], define_diskid[1], note);

        return false;

      } else {
        e.data.modal.update_form(data);
      }
    }, form.serialize());
  });
}

// Display backup restore modal window
function vm_backup_restore(hostname, btn, destroy_fun, rollback_fun) {
  if (btn.hasClass('disabled')) {
    return false;
  }

  var mod = $('#vm_snapshot_restore_modal');
  var err = mod.find('div.modal_error');
  var name = btn.parent().find('span.snapshot_name').html();
  var tr = btn.parent().parent();
  var disk_id = tr.data('disk_id');
  var disk_size = tr.data('disk_size');
  var vm_hostname = tr.data('hostname');
  var yes = mod.find('a.vm_modal_yes');
  var yes_force = mod.find('a.vm_modal_yes_force');
  var yes_force_default = yes_force.html();
  var text = mod.find('div.vm_modal_text');
  var text_default = text.html();
  var force_force = mod.find('span.vm_modal_force_force');
  var force_box = mod.find('#vm_snapshot_rollback_force');
  var target_hostname = $('#id_target_hostname');
  var target_disk_id = $('#id_target_disk_id');

  var text_filled = text_default.replace('__name__', name).replace('__disk_id__', disk_id).replace('__disk_size__', disk_size);

  if (!hostname) {
    text_filled = text_filled.replace('__hostname__', vm_hostname);
  }

  text.html(text_filled);
  err.hide();

  var handler = function() {
    if (!yes.hasClass('disabled')) {
      return destroy_fun(hostname, name, disk_id, vm_hostname);
    }
  };
  var handler_force = function() {
    if (!yes_force.hasClass('disabled')) {
      return rollback_fun(hostname, name, disk_id, force_box.prop('checked'), vm_hostname, target_hostname.val(), target_disk_id.val());
    }
  };
  var handler_force_box = function() {
    if (force_box.prop('checked')) {
      yes_force.removeClass('disabled', 400);
    } else {
      yes_force.addClass('disabled', 400);
    }
  };

  if (btn.data('rollback')) {
    force_force.addClass('hide');
    if (!yes_force.data('stay_disabled')) {
      yes_force.removeClass('disabled');
    }
  } else {
    yes_force.addClass('disabled');
    if (yes_force.data('stay_disabled')) {
      force_force.addClass('hide');
    } else {
      force_force.removeClass('hide');
      force_box.on('click', handler_force_box);
    }
  }

  mod.one('hide', function() {
    yes.off('click');
    yes_force.off('click');
    force_box.off('click');
    target_hostname.select2('destroy');
    target_disk_id.select2('destroy');
  });
  mod.one('hidden', function() {
    text.html(text_default);
    yes_force.html(yes_force_default);
    force_box.prop('checked', false);
  });

  yes.on('click', handler);
  yes_force.on('click', handler_force);

  function target_hostname_change() {
    var th = target_hostname.find(':selected').data('meta');

    if (th) {
      target_disk_id.empty();
      _.each(th['disks'], function(i) {
        var opt = $('<option></option>').attr('value', i[0]).text(i[1]);
        if (i[2] != disk_size) {
          opt.attr('disabled', 'disabled');
        }
        target_disk_id.append(opt);
      });
      target_disk_id.select2('val', '');
    }
  }

  target_disk_id.select2({dropdownCssClass: target_disk_id.attr('class')});
  target_hostname.select2({dropdownCssClass: target_hostname.attr('class')});
  target_hostname.off('change').change(target_hostname_change);
  target_hostname.select2('val', hostname);
  target_hostname_change();
  target_disk_id.select2('val', disk_id);

  activate_modal_ux(mod, mod.find('form'));
  mod.modal('show');
  MODAL = mod;
}

// Create image from snapshot modal
function vm_snapshot_image_modal(hostname, btn, snapname, disk_id) {
  obj_form_modal(btn, '#image_snapshot_modal', function(mod, start) {
    mod.form.find('#id_img-snapname').val(snapname);
    mod.form.find('#id_img-disk_id').val(disk_id);

    var alias = $('#id_img-alias');
    var name = $('#id_img-name');

    name.off('focusout').focusout(function() {
      if (!alias.val()) {
        alias.val(name.val());
      }
    });

  });
}

// Display rollback modal window
function vm_snapshot_rollback(hostname, btn, destroy_fun, rollback_fun) {
  if (btn.hasClass('disabled')) {
    return false;
  }

  var mod = $('#vm_snapshot_rollback_modal');
  var err = mod.find('div.modal_error');
  var name = btn.parent().find('span.snapshot_name').html();
  var tr = btn.parent().parent();
  var disk_id = tr.data('disk_id');
  var vm_hostname = tr.data('hostname');
  var yes = mod.find('a.vm_modal_yes');
  var yes_force = mod.find('a.vm_modal_yes_force');
  var yes_force_default = yes_force.html();
  var text = mod.find('div.vm_modal_text');
  var text_default = text.html();
  var force_force = mod.find('span.vm_modal_force_force');
  var force_box = mod.find('#vm_snapshot_rollback_force');
  var image_snapshot_link = mod.find('#image_snapshot_link');

  var text_filled = text_default.replace('__name__', name).replace('__disk_id__', disk_id);

  if (!hostname) {
    text_filled = text_filled.replace('__hostname__', vm_hostname);
  }

  text.html(text_filled);
  err.hide();

  var handler = function() {
    if (!yes.hasClass('disabled')) {
      return destroy_fun(hostname, name, disk_id, vm_hostname);
    }
  };
  var handler_force = function() {
    if (!yes_force.hasClass('disabled')) {
      return rollback_fun(hostname, name, disk_id, force_box.prop('checked'), vm_hostname);
    }
  };
  var handler_force_box = function() {
    if (force_box.prop('checked')) {
      yes_force.removeClass('disabled', 400);
    } else {
      yes_force.addClass('disabled', 400);
    }
  };

  if (btn.data('rollback')) {
    force_force.addClass('hide');
    if (!yes_force.data('stay_disabled')) {
      yes_force.removeClass('disabled');
    }
  } else {
    yes_force.addClass('disabled');
    if (yes_force.data('stay_disabled')) {
      force_force.addClass('hide');
    } else {
      force_force.removeClass('hide');
      force_box.on('click', handler_force_box);
    }
  }

  mod.one('hide', function() {
    yes.off('click');
    yes_force.off('click');
    force_box.off('click');
  });
  mod.one('hidden', function() {
    text.html(text_default);
    yes_force.html(yes_force_default);
    force_box.prop('checked', false);
  });

  yes.on('click', handler);
  yes_force.on('click', handler_force);

  if (image_snapshot_link.length) {
    image_snapshot_link.one('click', function() {
      mod.modal('hide');
      vm_snapshot_image_modal(hostname, image_snapshot_link, name, disk_id);
    });
  }

  activate_modal_ux(mod, mod.find('form'));
  mod.modal('show');
  MODAL = mod;
}

// Display snapshot change modal and perform snapshot information update
function vm_snapshot_update(hostname, btn) {
  if (btn.hasClass('disabled')) {
    return false;
  }

  var tr = btn.parent().parent();
  var mod = $('#vm_snapshot_update_modal');
  var form = mod.find('form');
  var form_default = form.html();
  var yes = mod.find('.vm_modal_yes');
  var select = mod.find('select.input-select2');
  var note = tr.find('small.vm_snapshot_note');
  disable_form_submit(form);

  form.find('#id_snap_update-name').val(tr.data('snapname'));
  form.find('#id_snap_update-disk_id').val(tr.data('disk_id'));
  form.find('#id_snap_update-note').val(note.text());
  if (!hostname) {
    form.find('#id_snap_update-hostname').val(tr.data('hostname'));
  }

  var handler = function() {
    form.find(':input').removeProp('disabled');

    ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, xhr) {
      if (xhr.status == 201) {
        note.html($(data).find('#id_snap_update-note').val());
        mod.modal('hide');
      } else if (xhr.status == 204) {
        mod.modal('hide');
      } else {
        form.html(data);
        select = $(select.selector);
        select.select2({dropdownCssClass: select.attr('class')});
      }
    }, form.serialize() + '&update=1');
  };

  mod.one('hide', function() {
    yes.off('click');
    select.select2('destroy');
  });
  mod.one('hidden', function() {
    if (form.length) {
      form.html(form_default);
      form[0].reset();
    }
  });
  yes.on('click', handler);
  select.select2({dropdownCssClass: select.attr('class')});

  activate_modal_ux(mod, form);
  mod.modal('show');
}

// Display multi delete modal window
function vm_snapshots_delete_modal(hostname, btn, gsio_handler) {
  if (VM_SNAPSHOTS.hostname !== hostname) {
    return false;
  }
  // TODO: BUG: btn.hasClass('disabled') is always true
  if (!VM_SNAPSHOTS.selected.length) {
    return false;
  }

  var mod = $('#vm_snapshots_delete_modal');
  var err = mod.find('div.modal_error');
  var disk_id = VM_SNAPSHOTS.selected[0].disk_id;
  var snapnames = _.pluck(VM_SNAPSHOTS.selected, 'snapname');
  var yes = mod.find('a.vm_modal_yes');
  var text = mod.find('div.vm_modal_text');
  var text_default = text.html();
  var vm_hostname = VM_SNAPSHOTS.vm_hostname;

  var text_filled = text_default.replace('__name__', snapnames.join(', ')).replace('__disk_id__', disk_id);

  if (!hostname) {
    text_filled = text_filled.replace('__hostname__', VM_SNAPSHOTS.vm_hostname);
  }

  text.html(text_filled);
  err.hide();

  var handler = function() {
    if (!yes.hasClass('disabled')) {
      gsio_handler(hostname, snapnames, disk_id, vm_hostname); // vm_destroy_snapshots
      VM_SNAPSHOTS.et.reset_selection();
    }
  };

  mod.one('hide', function() {
    yes.off('click');
  });
  mod.one('hidden', function() {
    text.html(text_default);
  });

  yes.on('click', handler);

  activate_modal_ux(mod, $.noop);
  mod.modal('show');
  MODAL = mod;
}

// Backup/Snapshot definition modal
function vm_snapshot_define_modal(hostname, btn, mod_selector) {
  if (btn.hasClass('disabled')) {
    return false;
  }

  var add = btn.hasClass('vm_add');
  if (add) {
    mod_selector += '_create';
  }
  var mod = $(mod_selector);
  var form = mod.find('form');
  var form_default = form.html();
  var btn_update = mod.find('a.vm_modal_update');
  var btn_delete = mod.find('a.vm_modal_delete');
  var btn_create = mod.find('a.vm_modal_create');
  var btn_more = mod.find('a.vm_modal_more');
  var select = mod.find('select.input-select2');
  disable_form_submit(form);

  function fix_form(f) {
    var bkp_type = f.find('#id_' + prefix + 'type');

    if (bkp_type.length) {
      var bkp_compression_field = f.find('#id_' + prefix + 'compression').parent().parent();

      var bkp_type_change = function() {
        if (bkp_type.val() == 1) {
          bkp_compression_field.hide();
        } else {
          bkp_compression_field.show();
        }
      };

      bkp_type.off('change').change(bkp_type_change);
      bkp_type_change();
    }
  }

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
        select.select2({dropdownCssClass: select.attr('class')});
        fix_form($(form.selector));
        if (mod.find('div.advanced div.input.error').length || btn_more.hasClass('active')) { morehandler(true); }
      }
    }, form.serialize() + '&siosid=' + get_siosid() + '&action=' + e.data.action);
  };

  var prefix = btn.data('prefix');

  if (prefix) {
    prefix += '-';
  } else {
    prefix = '';
  }

  if (!add) {
    var form_data = btn.data('form') || null;

    if (form_data) {
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

  fix_form(form);

  mod.one('hide', function() {
    btn_update.length && btn_update.off('click');
    btn_delete.length && btn_delete.off('click');
    btn_create.length && btn_create.off('click');
    if (btn_more.length) { btn_more.off('click'); morehandler(false); }
    select.select2('destroy');
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

  activate_modal_ux(mod, form);
  mod.modal('show');
}


/*********** eTable class *************/
function eTable(tbody_selector) {
  var self = this;
  var dt_options = {};
  this.enabled = true;
  this.dt = null;
  this.selected = {};
  this.elements = {
    'chbox_all':    $('#id_all'),
    'chbox_tr':     $(tbody_selector + ' input[type="checkbox"]:enabled'),
    'tbody_tr':     $(tbody_selector + ' tr'),
    'tfoot':        $('#etable_tfoot'),
    'table':        $('#etable'),
    'selected':     $('#selected'),
  };

  // **** ADD / DEL ****
  function row(chbox) {
    var tr = chbox.parent().parent().parent();
    var id = chbox.attr('id').substring(3);

    this.del = function() {
      chbox.prop('checked', false);
      tr.removeClass('highlight');
      delete self.selected[id];
    };

    this.add = function() {
      if (tr.is(':visible')) {
        chbox.prop('checked', true);
        tr.addClass('highlight');
        self.selected[id] = tr.data();
      }
    };

    return this;
  }

  // Show / Hide controls
  this.controls_show = function() {
    self.elements.tfoot.slideUp(400);
  };
  this.controls_hide = function() {
    self.elements.tfoot.slideDown(400);
  };

  // Show / Hide table controls/foot according to selected object
  this.toggle_controls = function() {
    if ($.isEmptyObject(self.selected)) {
      self.elements.selected.html(0);
      self.controls_hide();
    } else {
      self.elements.selected.html(_.size(self.selected));
      self.controls_show();
    }
  };

  // New table check operation
  this.reset_selection = function() {
    self.selected = {};
    self.elements.chbox_all.prop('checked', false);
    self.elements.chbox_tr.prop('checked', false);
    self.elements.tbody_tr.removeClass('highlight');
    self.toggle_controls();
  };

  // Destroy data table
  this.destroy = function() {
    self.reset_selection();
  };

  // Initialize data table
  this.init = function() {
  };

  // **** START ****
  this.reset_selection();

  // **** ALL ****
  this.elements.chbox_all.click(function(e) {
    if (!self.enabled) { return false; }

    var chbox = $(this);

    if (chbox.prop('checked')) {
      self.elements.chbox_tr.each(function() {
        row($(this)).add();
      });
    } else {
      self.elements.chbox_tr.each(function() {
        row($(this)).del();
      });
    }

    self.toggle_controls();

    return true;
  });

  // **** CHBOX ****
  this.elements.chbox_tr.click(function(e) {
    if (!self.enabled) { return false; }

    var chbox = $(this);

    if (chbox.prop('checked')) {
      row(chbox).add();
    } else {
      self.elements.chbox_all.prop('checked', false);
      row(chbox).del();
    }

    self.toggle_controls();

    return true;
  });

} // eTable()

var VM_SNAPSHOTS = null;

function _SnapshotList(hostname, snaplist) {
  var self = this;
  var _hostname = _jq(hostname);
  var snaps_del = $('#vm_snapshots_del_' + _hostname + ', #vm_backups_del_' + _hostname);

  this.hostname = hostname;
  this.et = new eTable('#vm_snaplist_' + _hostname);
  this.selected = [];
  this.vm_hostname = null;

  // Modify function for empty selection
  this.et.controls_hide = function() {
    self.selected = [];
    self.vm_hostname = null;  // Used for no VM backups
    snaps_del.addClass('disabled');
  };

  // Modify function for non-empty selection
  this.et.controls_show = function() {
    var selected = _.values(this.selected);
    var first = _.first(selected);
    var compare_fun = function(i) {
      return (i.disk_id === first.disk_id && i.status === first.status && i.hostname === first.hostname && i.type === first.type);
    };

    // Check if all selected snapshots have the same disk_id and status
    if (_.every(selected, compare_fun)) {
      snaps_del.removeClass('disabled');
      self.selected = selected;
      self.vm_hostname = first.hostname;
    } else {
      snaps_del.addClass('disabled');
      self.selected = [];
      self.vm_hostname = null;
    }
  };

  // Toggle snapshot delete button from outside
  this.control_toggle = function(hostname, enabled) {
    // Disabled checkboxes
    self.et.enabled = enabled;

    // Toggle snapshot delete only if enabled!
    if (enabled) {
      if (hostname === self.hostname) {
        self.et.toggle_controls();
      }
    }
  };

  // The end
  this.destroy = function() {
    self.et.destroy();
    delete self.et;
  };

  // Start
  vm_snapshot_define_links(hostname);
  vm_snapshot_list_links(hostname, snaplist);
  obj_list_sort_db(this.et.elements.table);

} // _SnapshotList
function create_snapshot_list(hostname) {
  VM_SNAPSHOTS = new _SnapshotList(hostname, $(jq('vm_snapshots_' + hostname)));
  return VM_SNAPSHOTS;
}
function create_backup_list(hostname) {
  VM_SNAPSHOTS = new _SnapshotList(hostname, $(jq('vm_backups_' + hostname)));
  return VM_SNAPSHOTS;
}
