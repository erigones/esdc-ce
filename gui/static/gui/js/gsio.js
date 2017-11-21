var LAST_TASKS = {};

/************ VM CONTROL ************/
// Get VM definition
function vm_define(hostname, kwargs) {
  if (typeof(kwargs) === 'undefined') {
    kwargs = {};
  }
  return esio('get', 'vm_define', [hostname], {'data': kwargs});
}

// Start VM (with optional cdimage)
function vm_start(hostname, cdimage, update, onetime, cdimage2) {
  var kwargs = {'action': 'start', 'data': {}};
  if (cdimage) {
    kwargs['data']['cdimage'] = cdimage;
  }
  if (typeof(update) !== 'undefined') {
    kwargs['data']['update'] = update;
  }
  if (typeof(onetime) !== 'undefined') {
    kwargs['data']['cdimage_once'] = onetime;
    if (cdimage2) {
      kwargs['data']['cdimage2'] = cdimage2;
    }
  }
  return esio('set', 'vm_status', [hostname], kwargs);
}

// Stop or reboot VM (with optional force boolean)
function vm_stop_or_reboot(hostname, action, force, timeout) {
  var kwargs = {'action': action};
  if (force) {
    kwargs['data'] = {'force': true};
  }
  else if (typeof(timeout) !== 'undefined' && timeout) {
    kwargs['data'] = {'timeout': timeout};
  }
  return esio('set', 'vm_status', [hostname], kwargs);
}

// Stop and freeze/unfreeze VM (with optional force boolean)
function vm_freeze(hostname, freeze, force, timeout) {
  var kwargs = {'action': 'stop', 'data': {}};
  if (freeze) {
    kwargs['data']['freeze'] = true;
  } else {
    kwargs['data']['unfreeze'] = true;
  }
  if (force) {
    kwargs['data']['force'] = true;
  }
  else if (typeof(timeout) !== 'undefined' && timeout) {
    kwargs['data']['timeout'] = timeout;
  }
  return esio('set', 'vm_status', [hostname], kwargs);
}

// Create disk snapshot
function vm_create_snapshot(hostname, snapname, disk_id, fsfreeze, note) {
  var kwargs = {'data': {}};
  if (typeof(disk_id) !== 'undefined' && (disk_id)) {
    kwargs['data']['disk_id'] = disk_id;
  }
  if (typeof(fsfreeze) !== 'undefined' && (fsfreeze)) {
    kwargs['data']['fsfreeze'] = fsfreeze;
  }
  if (typeof(note) !== 'undefined' && (note)) {
    kwargs['data']['note'] = note;
  }
  return esio('create', 'vm_snapshot', [hostname, snapname], kwargs);
}

// Rollback disk snapshot
function vm_rollback_snapshot(hostname, snapname, disk_id, force) {
  var kwargs = {'data': {}};
  if (typeof(disk_id) !== 'undefined' && (disk_id)) {
    kwargs['data']['disk_id'] = disk_id;
  }
  if (typeof(force) !== 'undefined') {
    kwargs['data']['force'] = force;
  }
  return esio('set', 'vm_snapshot', [hostname, snapname], kwargs);
}

// Destroy disk snapshot
function vm_destroy_snapshot(hostname, snapname, disk_id) {
  var kwargs = {'data': {}};
  if (typeof(disk_id) !== 'undefined' && (disk_id)) {
    kwargs['data']['disk_id'] = disk_id;
  }
  return esio('delete', 'vm_snapshot', [hostname, snapname], kwargs);
}

// Destroy multiple disk snapshots
function vm_destroy_snapshots(hostname, snapnames, disk_id) {
  var kwargs = {'data': {'disk_id': disk_id, 'snapnames': snapnames}};
  return esio('delete', 'vm_snapshot_list', [hostname], kwargs);
}

// Create disk backup
function vm_create_backup(hostname, bkpdef, disk_id, note) {
  var kwargs = {'data': {}};
  if (typeof(disk_id) !== 'undefined' && (disk_id)) {
    kwargs['data']['disk_id'] = disk_id;
  }
  if (typeof(note) !== 'undefined' && (note)) {
    kwargs['data']['note'] = note;
  }
  return esio('create', 'vm_backup', [hostname, bkpdef], kwargs);
}

// Destroy disk backup
function vm_destroy_backup(hostname, bkpname, disk_id, vm_hostname) {
  var kwargs = {'data': {}};
  if (typeof(disk_id) !== 'undefined' && (disk_id)) {
    kwargs['data']['disk_id'] = disk_id;
  }
  if (vm_hostname) {
    hostname = vm_hostname;
    kwargs['data']['hostname'] = hostname;
  }
  return esio('delete', 'vm_backup', [hostname, bkpname], kwargs);
}

// Destroy multiple disk backups
function vm_destroy_backups(hostname, bkpnames, disk_id, vm_hostname) {
  var kwargs = {'data': {'disk_id': disk_id, 'bkpnames': bkpnames}};
  if (vm_hostname) {
    hostname = vm_hostname;
    kwargs['data']['hostname'] = hostname;
  }
  return esio('delete', 'vm_backup_list', [hostname], kwargs);
}

// Restore disk backup
function vm_restore_backup(hostname, bkpname, disk_id, force, vm_hostname, target_hostname, target_disk_id) {
  var kwargs = {'data': {'disk_id': disk_id}};
  kwargs['data']['vm'] = Boolean(hostname);  // Information is used by message_callback and is not used by the api call
  if (vm_hostname) {
    hostname = vm_hostname;
    kwargs['data']['hostname'] = hostname;
  }
  if (typeof(force) !== 'undefined') {
    kwargs['data']['force'] = force;
  }
  if (typeof(target_hostname) !== 'undefined' && target_hostname) {
    kwargs['data']['target_hostname_or_uuid'] = target_hostname;
  }
  if (typeof(target_disk_id) !== 'undefined' && target_disk_id) {
    kwargs['data']['target_disk_id'] = target_disk_id;
  }
  return esio('set', 'vm_backup', [hostname, bkpname], kwargs);
}

// Factory reset -> delete and create VM
function vm_recreate(hostname, force) {
  var kwargs = {'data': {'recreate': true}};
  if (typeof(force) !== 'undefined') {
    kwargs['data']['force'] = force;
  }
  return esio('create', 'vm_manage', [hostname], kwargs);
}

// Update VM on compute node
function vm_update(hostname) {
  return esio('set', 'vm_manage', [hostname]);
}

// Create VM on compute node
function vm_create(hostname) {
  return esio('create', 'vm_manage', [hostname]);
}

// Delete VM from compute node
function vm_delete(hostname) {
  return esio('delete', 'vm_manage', [hostname]);
}

// Migrate VM to another compute node
function vm_migrate(hostname, node) {
  return esio('set', 'vm_migrate', [hostname], {'data': {'node': node}});
}

// Fail over VM to its replica
function vm_replica_failover(hostname, repname, force) {
  var kwargs = {'data': {}};
  if (force) {
    kwargs['data']['force'] = true;
  }
  return esio('set', 'vm_replica_failover', [hostname, repname], kwargs);
}

// Reinitialize VM replication after failover
function vm_replica_reinit(hostname, repname) {
  return esio('set', 'vm_replica_reinit', [hostname, repname]);
}

// Get VM/Node SLA
function get_sla(view_name, hostname, yyyymm) {
  // This runs in background, so do not run if not connected
  if (SOCKET.socket.connected) {
    return esio('get', view_name, [hostname, yyyymm]);
  }
  return null;
}

// Get Node or VM monitoring history (obj_type = {vm|node})
function mon_get_history(obj_type, hostname, graph, data) {
  var kwargs = {'data': {}};
  if (typeof(data) !== 'undefined') {
    kwargs['data'] = data;
  }
  // This runs in background, so do not run if not connected
  if (SOCKET.socket.connected) {
    return esio('get', 'mon_'+ obj_type +'_history', [hostname, graph], kwargs);
  }
  return null;
}

function mon_get_alerts(hostname, data) {
  var args = [];
  var kwargs = {'data': {}};
  //if (typeof(data) !== 'undefined') {
  //  kwargs['data'] = data;
  //}
  return esio('get', 'mon_alert_list', args, kwargs);
}

// Delete image from Node storage
function node_delete_image(hostname, zpool, image_name) {
  return esio('delete', 'node_image', [hostname, zpool, image_name]);
}

// Delete all unused images from Node storage
function node_cleanup_images(hostname, zpool) {
  return esio('delete', 'node_image_list', [hostname, zpool]);
}

// Refresh the information about the node by running sysinfo
function node_sysinfo(hostname) {
  return esio('set', 'node_sysinfo', [hostname]);
}

/************ CALLBACKS ************/
// just a helper for changing all 3 visual controls
function _update_vm_visuals(hostname, status_display, apiview) {
  // If there is a server status label, then we need to update it
  vm_label_update(hostname, status_display, apiview);
  // If there is a server status badge, then we need to update it
  vm_badge_update(hostname, status_display);
  // If there is a server control panel, then we need to show/hide it and update it
  vm_control_update(hostname, status_display, apiview);
  // If user is watching a server console window, then we might want to reload it (depending on server status)
  vm_vnc_update(hostname, status_display);
}

// just a helper for getting serializer error message array
function _sererror_from_result(res) {
  var msg;

  if (res.detail) {
    msg = [res.detail];
  } else if (res.result) {
    if (typeof(res.result) == 'object') {
      msg = [];
      for (var key in res.result) {
        var val = res.result[key];
        if ($.isArray(val)) {
          $.merge(msg, val);
        } else {
          msg.push(val);
        }
      }
    } else {
      msg = [res.result];
    }
  } else {
    msg = [res];
  }

  return msg;
}

// just a helper for getting error message
function _message_from_result(res) {
  // REVOKED: we don't have a message
  if (res.status == 'REVOKED') {
    return 'Task ' + res.result; // result is "expired" or "terminated"
  }

  // FAILURE: we need to find the right error message
  var msg = res;

  if (res.detail) {
    msg = res.detail;
  } else if (res.result) {
    msg = res.result;

    if (typeof(msg) == 'object') {
      if (msg.message) {
        msg = msg.message;
      } else if (msg.detail) {
        msg = msg.detail;
      } else {
        try {
          msg = JSON.stringify(msg, null, 4);
        } catch(e) {
          console.log(e);
        }
      }
    }
  }

  if (typeof(msg) == 'object') {
    // The string version for this msg is "[object Object]" and we don't want to show that to user
    console.log('Unknown error - maybe the task was deleted?');
    msg = 'Unknown error';
  }

  return String(msg);
}

// Get task prefix
function task_prefix_from_task_id(task_id) {
  return task_id.split(/([a-zA-Z-]+)/).slice(0,5);
}

// Display error message
function alert_message(code, err_msg) {
  if (code == 428) {
    alert2(gettext(err_msg)); // More friendly way to display errors from api
  } else {
    notify('error', err_msg + ' (' + code + ')');
  }
}

// callback: "error"
function error_callback(error_name, error_message) {
  if (typeof(error_message) !== 'undefined' && error_message) {
    // Always alert - socket.io want's to say something
    alert2(error_message);

  } else if (typeof(error_name) !== 'undefined' && error_name) {
    // Alert only if still not connected after 1 sec. delay
    setTimeout(function() {
      if (!SOCKET.socket.connected) {
        alert2(gettext('Socket.io connection error.'));
      }
    }, 1000);

  } else {
    // Alert only if javascript debugging is disabled
    if (DEBUG) {
      console.log('Socket.io connection problem.');
    } else {
      alert2(gettext('Socket.io connection problem. Please try again later.'));
    }
  }
}

// callback: "info"
function info_callback(sender, args, kwargs) {
  switch (sender) {
    case 'dc_switch':
      alert2(gettext('Your current datacenter was changed by another user session. Please refresh your browser.'));
      break;
  }
}

// callback: "connect"
function connect_callback(e) {
  $('#sio-status').removeClass('red').addClass('green');
}

// callback: "disconnect"
function disconnect_callback(e) {
  $('#sio-status').removeClass('green').addClass('red');
}

function update_sio_status() {
  if (SOCKET.socket.connected) {
    connect_callback();
  } else {
    disconnect_callback();
  }

  $('#sio-status').click(function(e) {
    e.preventDefault();
    if (!SOCKET.socket.connected && !SOCKET.socket.connecting) {
      SOCKET.socket.connect();
    }
    return false;
  });
}

// callback: "message"
function message_callback(code, res, view, method, args, kwargs, apiview, apidata) {
  var hostname = apiview.hostname || kwargs.hostname || kwargs.hostname_or_uuid || args[0] || null;
  var target_hostname = hostname;  // get target_hostname (real VM)
  var data = kwargs;
  var task_id = res.task_id || null;
  var state;

  if (task_id && task_id in LAST_TASKS) {
    console.log('Ignoring task', task_id);
    return false;
  }

  if ('view' in apiview) {
    view = apiview.view;
  }

  if ('data' in kwargs) {
    data = kwargs.data;
  }

  if ('target_hostname' in apiview) {
    target_hostname = apiview.target_hostname;
  } else if ('target_hostname' in data) {
    target_hostname = data.target_hostname;
  } else if ('target_hostname_or_uuid' in data) {
    target_hostname = data.target_hostname_or_uuid;
  }

  // always update task list if it exists
  var t = vm_tasks(target_hostname, res, view, method);

  if (res.status == 'PENDING' || res.status == 'STARTED') {
    switch (view) {
      case 'vm_status': // vm_status started
        if (method == 'PUT') {
          var transition_status = 'pending';

          if (apidata.status_display == 'stopping') {
            transition_status = 'stopping';
          }
          _update_vm_visuals(hostname, transition_status);
        }
        break;

      case 'vm_manage': // vm_manage started
        if (method == 'POST') {
          _update_vm_visuals(hostname, 'creating');
          vm_define(hostname, {'node': true}); // Bug #399 - node could be chosen automatically -> need to update GUI
        } else {
          _update_vm_visuals(hostname, vm_status_display_notready(hostname));
        }
        break;

      case 'vm_snapshot': // vm_snapshot started
        if (method == 'DELETE' || method == 'PUT') {
          vm_snapshot_modal_update(hostname, null); // hide modal if shown
        }

        if (method == 'PUT') { // is a rollback in progress?
          if (target_hostname && hostname != target_hostname) {
            // restore to another VM -> update source VM's status and list of snapshots
            state = vm_status_display_notready(hostname);
            _update_vm_visuals(hostname, state);
            vm_snapshots_update(hostname, state);
          } else {
            // the target VM must be in stopped- (notready) state
            target_hostname = hostname; // just in case; should be assert
          }
          // status changed to stopped- in DB (notready)
          _update_vm_visuals(target_hostname, 'stopped-');
          // if there is a list of snapshots/backups, then we need to update it
          vm_snapshots_update(target_hostname, 'stopped-');
        } else { // create/delete snapshot in progress
          // if there is a list of snapshots/backups, then we need to update it
          vm_snapshots_update(hostname, null);
        }
        break;

      case 'vm_snapshot_list': // vm_snapshot_list started
        if (method == 'DELETE') {
          vm_snapshot_modal_update(hostname, null); // hide modal if shown
          // if there is a list of snapshots/backups, then we need to update it
          vm_snapshots_update(hostname, null);
        }
        break;

      case 'vm_backup': // vm_backup started
      case 'vm_backup_list': // vm_backup_list started
        state = null; // used in vm_snaphosts_update

        if (method == 'PUT') { // a restore is in progress
          if (hostname == target_hostname) {
            // also update status in vm_backups_update() below
            state = 'stopped-';
          }

          // do not need to update the list, but the status of target VM changed to stopped- in DB (notready)
          _update_vm_visuals(target_hostname, 'stopped-');
        }

        if (method == 'DELETE' || method == 'PUT') {
          if ((method == 'PUT') && !data.vm) { // -> object is backup node or target VM and source VM does not exist anymore
            hostname = '';
          }
          vm_backup_modal_update(hostname, null); // hide modal if shown (empty hostname is OK)
        }

        // if there is a list of snapshots/backups, then we need to update it
        vm_backups_update(hostname, state); // empty hostname is OK (DELETE or PUT)
        break;

      case 'vm_migrate': // vm_migrate started
        if (method == 'PUT') {
          // status changed to stopped- in DB (notready)
          _update_vm_visuals(hostname, vm_status_display_notready(hostname));
          vm_migrate_update(hostname, true);
        }
        break;

      case 'vm_replica': // vm_replica started
        if (method == 'POST') {
          // status changed to stopped- or running- in DB (notready)
          _update_vm_visuals(hostname, vm_status_display_notready(hostname));
        }
        break;

      case 'vm_replica_failover': // vm_replica_failover started
        // status changed to stopped- or running- in DB (notready)
        _update_vm_visuals(hostname, vm_status_display_notready(hostname));
        // hide modal window if shown
        vm_replica_modal_update(hostname, null);
        break;

      case 'vm_replica_reinit': // vm_replica_reinit started
        // hide modal window if shown
        vm_replica_modal_update(hostname, null);
        break;

      case 'vm_screenshot': // vm_screenshot failed
        return; // do not update cached_tasklog

      case 'mon_vm_sla': // mon_vm_sla started
      case 'mon_node_sla':
        return; // do not update cached_tasklog

      case 'mon_alert_list': // mon_vm_sla started
        return; // do not update cached_tasklog

      case 'mon_vm_history': // mon_vm_history started
      case 'mon_node_history': // mon_node_history started
        return; // do not update cached_tasklog

      case 'mon_template_list': // mon_template_list started
      case 'mon_node_template_list':
      case 'mon_hostgroup_list': // mon_hostgroup_list started
      case 'mon_node_hostgroup_list':
        return; // do not update cached_tasklog

      case 'node_image': // node_image started
        if (method == 'DELETE') { // POST node_image() will not affect DB, so not update is needed (except tasklog)
          node_image_update(args[0], args[1] || kwargs.zpool, args[2] || kwargs.name, false, 3, 'deleting');
        }
        break;

      case 'image_snapshot': // image_snapshot started
        // if there is a list of snapshots, then we need to update it
        vm_snapshots_update(hostname, null);
        break;

      case 'image_manage': // image_manage started
        // Update image list
        image_list_update(kwargs.name, false, 2, 'pending');
        break;
    }

  // all FAILURE -> send notification
  } else if ((res.status == 'FAILURE') || (code >= 400)) {

    switch (view) {
      case 'vm_define': // vm_define GET failed -> ignore
        return; // do not update cached_tasklog

      case 'vm_screenshot': // vm_screenshot failed
        notify('error', _message_from_result(res) + ' (' + code + ')');
        return; // do not update cached_tasklog

      case 'mon_vm_sla': // mon_vm_sla failed
      case 'mon_node_sla':
        sla_update(view, args[0], args[1], null);
        return; // do not update cached_tasklog

      case 'mon_alert_list': // mon_vm_sla failed
        alert_update(view, args[0], args[1], null);
        return; // do not update cached_tasklog

      case 'mon_vm_history': // mon_vm_history failed
      case 'mon_node_history': // mon_node_history failed
        mon_history_update(view.split('_', 2)[1], args[0], args[1], data, null, _message_from_result(res));
        return; // do not update cached_tasklog

      case 'mon_template_list': // mon_template_list failed
      case 'mon_node_template_list':
      case 'mon_hostgroup_list': // mon_hostgroup_list failed
      case 'mon_node_hostgroup_list':
        return; // do not update cached_tasklog

      case 'vm_backup': // vm_backup failed
        if (method == 'DELETE' || method == 'PUT') {
          vm_backup_modal_update(hostname, _sererror_from_result(res)); // show error
        } else {
          alert_message(code, _message_from_result(res));
        }
        return; // do not update cached_tasklog

      case 'vm_snapshot': // vm_snapshot failed
        if (method == 'DELETE' || method == 'PUT') {
          vm_snapshot_modal_update(hostname, _sererror_from_result(res)); // show error
        } else {
          alert_message(code, _message_from_result(res));
        }
        return; // do not update cached_tasklog

      case 'vm_backup_list': // vm_backup_list failed
        if (method == 'DELETE') {
          vm_backup_modal_update(hostname, _sererror_from_result(res)); // show error
        } else {
          alert_message(code, _message_from_result(res));
        }
        return; // do not update cached_tasklog

      case 'vm_snapshot_list': // vm_snapshot_list failed
        if (method == 'DELETE') {
          vm_snapshot_modal_update(hostname, _sererror_from_result(res)); // show error
        } else {
          alert_message(code, _message_from_result(res));
        }
        return; // do not update cached_tasklog

      case 'vm_migrate': // vm_migrate did not start, because of an error
        vm_migrate_update(hostname, false, _sererror_from_result(res));
        return; // do not update cached_tasklog

      case 'vm_replica_failover': // vm_replica_failover did not start, because of an error
      case 'vm_replica_reinit': // vm_replica_reinit did not start, because of an error
        vm_replica_modal_update(hostname, _sererror_from_result(res));
        return; // do not update cached_tasklog

      case 'node_image_list': // DELETE node_image_list failed (node is not ready?)
        alert_message(code, _message_from_result(res));
        return; // do not update cached_tasklog

      default:
        alert_message(code, _message_from_result(res));
        return; // do not update cached_tasklog
    }

  // mgmt tasks with cached result - SUCCESS
  } else if (res.status == 'SUCCESS') {
    switch (view) {
      case 'vm_define': // someone called vm_define to update some VM info
        vm_define_update(hostname, res.result, kwargs);
        return; // do not update cached_tasklog

      case 'vm_manage':
        if (method == 'PUT') { // PUT vm_manage can be run without creating real task
          notify('success', res.result);
        }
        break;

      case 'vm_snapshot':
      case 'vm_snapshot_list':
        if (method == 'DELETE') { // DELETED lost snapshot(s)
          vm_snapshot_modal_update(hostname, null); // hide modal if shown
          // if there is a list of snapshots, then we need to update it
          vm_snapshots_update(hostname, null);
        }
        break;

      case 'vm_backup':
      case 'vm_backup_list':
        if (method == 'DELETE') { // DELETED lost backup(s)
          vm_backup_modal_update(hostname, null); // hide modal if shown
          // if there is a list of backups, then we need to update it
          vm_backups_update(hostname, null);
        }
        break;

      case 'vm_screenshot': // vm_screenshot success (impossible)
        return; // do not update cached_tasklog

      case 'node_image_list': // DELETE node_image_list finished
        return; // do not update cached_tasklog

      case 'mon_vm_sla': // mon_vm_sla result from cache
      case 'mon_node_sla':
        sla_update(view, args[0], args[1], res.result);
        return; // do not update cached_tasklog

      case 'mon_alert_list': // mon_vm_sla result from cache
        alert_update(view, args[0], args[1], res.result);
        return; // do not update cached_tasklog

      case 'mon_vm_history': // mon_vm_history result from cache
      case 'mon_node_history': // mon_node_history result from cache
        mon_history_update(view.split('_', 2)[1], args[0], args[1], data, res.result);
        return; // do not update cached_tasklog

      case 'mon_template_list': // mon_template_list result from cache
      case 'mon_node_template_list':
        mon_templates_update(res.result);
        return; // do not update cached_tasklog
      case 'mon_hostgroup_list': // mon_hostgroup_list result from cache
        mon_hostgroups_update(res.result);
        return; // do not update cached_tasklog
      case 'mon_node_hostgroup_list':
        mon_node_hostgroups_update(res.result);
        return; // do not update cached_tasklog
    }
  }

  // always update cached_tasklog
  update_tasklog_cached();
}


// Real task-event callback
function _task_event_callback(result) {
  var hostname = result.hostname || null;
  var siosid = get_siosid();

  switch (result._event_) {
    case 'vm_status_changed': // server status changed
      if (result.status_display != 'unknown') {
        notify('info', gettext('Server') +' '+ result.alias +' '+ gettext('changed status to') +' '+ gettext(result.status_display));
      }
      _update_vm_visuals(hostname, result.status_display, result);
      break;

    case 'vm_define_hostname_changed': // server hostname changed
      if (result.siosid != siosid) { // Inform only other users
        alert2(result.message);
      }
      break;

    case 'vm_replica_synced': // replica sync event
      vm_replica_status_update(hostname, result);
      return false;  // do not update cached tasklog

    case 'node_status_changed': // node changed status
      if (result.siosid != siosid) { // Inform only other users
        node_status_update(hostname, result.status, result.status_display); // Reload node details page if displayed
      }
      break;

    case 'system_reloaded': // SystemReloaded event called from SystemReloadThread
      alert2(result.message);
      break;

    case 'user_current_dc_changed':
      alert2(gettext('Your current datacenter was changed. Please log out and log in again or <a class="btn-link" href="/">navigate to the default page</a>.'));
      break;

    default: // send notification
      if (typeof(result.message) !== 'undefined') {
        notify('info', result.message);
      }
      break;
  }

  return true; // true => update cached tasklog
}

// callback: "task_event"
function task_event_callback(result) {
  // Dispatched event from API or GUI
  if (_task_event_callback(result)) {
    // update cached_tasklog
    update_tasklog_cached();
  }
}


// task_status_callback for classic task events
function _task_status_callback(res, apiview) {
  var result = res.result || {};
  var hostname = apiview.hostname || null;
  var msg = '';
  var task_prefix = '';
  var state;

  // always update task list if it exists and if apiview.hostname is defined
  var t = vm_tasks(apiview.hostname || null, res, apiview.view, apiview.method);

  // SUCCESS or FAILURE by view name
  switch (apiview.view) {

    case 'vm_status':
      if (res.status == 'SUCCESS') {
        var result_msg = result.message || '';
        // Sometimes the vm configuration gets updated during vm_status.
        // If this happens we should refresh server details page (see vm_manage below)
        if (result_msg.indexOf('Successfully updated') >= 0 && t) {
          vm_refresh_page(hostname);
        }

      } else { // FAILURE or REVOKED
        // something went wrong, there is no point to wait for the vm_status_changed action
        _update_vm_visuals(hostname, apiview.status_display, apiview);
        // Inform user with message
        notify('error', _message_from_result(res));
      }
      break;


    case 'vm_snapshot':
    case 'vm_snapshot_list':
      // if there is a list of snapshots, then we need to update it
      vm_snapshots_update(hostname, apiview.status_display, apiview.snapname, apiview.disk_id);

      if (apiview.method == 'PUT') {
        if (apiview.view == 'vm_snapshot_list') { // vm_snapshot_sync (PUT vm_snapshot_list)

          if (res.status == 'SUCCESS') {
            notify('success', gettext(result.message));
          } else {
            notify('error', _message_from_result(res));
          }
          break;

        } else {
          if (apiview.source_hostname && apiview.source_hostname != hostname) { // -> restore to another VM
            // get source VM status
            state = vm_status_display_revert_notready(apiview.source_hostname);
            // if there is a list of snapshots on the source VM, then we need to update it (rollback status)
            vm_snapshots_update(apiview.source_hostname, state, apiview.snapname, apiview.disk_id);
            if (state) {
              // also the source VM was in notready state -> update this
              _update_vm_visuals(apiview.source_hostname, state);
            }
          }
          // doing a rollback (PUT vm_snapshot)
          _update_vm_visuals(hostname, apiview.status_display, apiview);
        }
      }

      task_prefix = task_prefix_from_task_id(res.task_id);

      if (!task_prefix || task_prefix[1] !== 'a') {  // Display message only if task is not auto/cron task
        if (res.status == 'SUCCESS' && result.returncode == '0') {
          switch(apiview.method) {
            case 'POST':
              msg = gettext('Snapshot successfully created');
              break;
            case 'DELETE':
              msg = gettext('Snapshot successfully deleted');
              break;
            case 'PUT':
              msg = gettext('Snapshot successfully restored');
              break;
          }
          notify('success', msg);

        } else if (res.status == 'FAILURE') {
          switch(apiview.method) {
            case 'POST':
              msg = gettext('Creating new snapshot failed');
              break;
            case 'DELETE':
              msg = gettext('Deleting snapshot failed');
              break;
            case 'PUT':
              msg = gettext('Restoring snapshot failed');
              break;
          }
          notify('error', msg);

        } else { // REVOKED
          notify('error', _message_from_result(res));
        }
      }

      break;


    case 'vm_backup':
    case 'vm_backup_list':
      state = apiview.status_display || null;

      // doing a restore
      if (apiview.method == 'PUT') {
        // status of target VM changed from stopped- (notready) to some real state
        _update_vm_visuals(hostname, apiview.status_display, apiview);

        if (apiview.source_hostname != hostname) { // -> restore to another VM
          state = null;
          // vm_backups_update() below updates list backups of source VM
          hostname = apiview.source_hostname;
        }
      }

      if (apiview.method == 'DELETE' || apiview.method == 'PUT') {
        if (!apiview.vm) { // -> object is backup node or target VM and source VM does not exist anymore
          hostname = '';
          state = null;
        }
      }

      // if there is a list of backups, then we need to update it
      vm_backups_update(hostname, state, apiview.bkpname || null, apiview.disk_id);

      task_prefix = task_prefix_from_task_id(res.task_id);

      if (!task_prefix || task_prefix[1] !== 'a') {  // Display message only if task is not auto/cron task
        if (res.status == 'SUCCESS' && result.returncode == '0') {
          switch(apiview.method) {
            case 'POST':
              msg = gettext('Backup successfully created');
              break;
            case 'DELETE':
              msg = gettext('Backup successfully deleted');
              break;
            case 'PUT':
              msg = gettext('Backup successfully restored');
              break;
          }
          notify('success', msg);

        } else if (res.status == 'FAILURE') {
          switch(apiview.method) {
            case 'POST':
              msg = gettext('Creating new backup failed');
              break;
            case 'DELETE':
              msg = gettext('Deleting backup failed');
              break;
            case 'PUT':
              msg = gettext('Restoring backup failed');
              break;
          }
          notify('error', msg);

        } else { // REVOKED
          notify('error', _message_from_result(res));
        }
      }

      break;


    case 'vm_manage':
      _update_vm_visuals(hostname, apiview.status_display, apiview);

      if (res.status == 'SUCCESS') {
        if (result.message) {
          notify('success', gettext(result.message));
        }
      } else { // FAILURE or REVOKED
        notify('error', _message_from_result(res));
      }

      // Reload server details page after vm_manage
      if (t) { vm_refresh_page(hostname); }
      break;

    case 'vm_migrate':
      _update_vm_visuals(hostname, apiview.status_display, apiview);
      // Reload server details page after successful vm_migrate
      if (res.status == 'SUCCESS') {
        notify('success', gettext(result.message));
        var refreshed = false;

        if (t) {
          refreshed = vm_refresh_page(hostname);
        }

        if (!refreshed) { // Try to update node hostname/color if on server list page
          vm_define(hostname, {'node': true});
        }
      } else {
        notify('error', _message_from_result(res));
      }
      break;

    case 'vm_replica':
    case 'vm_replica_reinit':
      if (apiview.method == 'POST' || apiview.method == 'DELETE') {  // create, delete or reinit replica
        // Update VM locked status
        _update_vm_visuals(hostname, apiview.status_display, apiview);
      }

      // Display success or error message
      if (res.status == 'SUCCESS') {
        notify('success', gettext(result.message));
        // Update VM replica status if displayed
        vm_replica_status_update(hostname, result);
        // Update VM replication button
        vm_replica_control_update(hostname, result);
      } else {
        notify('error', _message_from_result(res));
      }
      break;

    case 'vm_replica_failover':
      // Status changed back from notready
      _update_vm_visuals(hostname, apiview.status_display, apiview);
      // Reload server details page after successful vm_replica_failover
      if (res.status == 'SUCCESS') {
        notify('success', gettext(result.message));
        if (t) { vm_refresh_page(hostname); }
      } else {
        notify('error', _message_from_result(res));
      }
      break;


    case 'vm_screenshot':
      return false; // do not update cached_tasklog

    case 'mon_vm_sla':
    case 'mon_node_sla':
      if (res.status != 'SUCCESS') {
        result = null;
      }
      sla_update(apiview.view, hostname, apiview.yyyymm, result);
      return false; // do not update cached_tasklog

   case 'mon_alert_list':
      if (res.status != 'SUCCESS') {
        result = null;
      }
      alert_update(apiview.view, hostname, apiview.yyyymm, result);
      return false; // do not update cached_tasklog

    case 'mon_vm_history':
    case 'mon_node_history':
      var obj_type = apiview.view.split('_', 2)[1];
      var error = null;

      if (res.status != 'SUCCESS') {
        result = null;
        error = _message_from_result(res);
      }

      mon_history_update(obj_type, hostname, apiview.graph, apiview.graph_params, result, error);

      return false; // do not update cached_tasklog

    case 'mon_template_list':
    case 'mon_node_template_list':
      if (res.status == 'SUCCESS') {
        mon_templates_update(result);
      }
      return false; // do not update cached_tasklog
    case 'mon_hostgroup_list':
      if (res.status == 'SUCCESS') {
        mon_hostgroups_update(result);
        mon_node_hostgroups_update(result);

      }
      return false; // do not update cached_tasklog
    /*case 'mon_node_hostgroup_list':
      if (res.status == 'SUCCESS') {
        mon_node_hostgroups_update(result);
      }
      return false; // do not update cached_tasklog
    */

    case 'node_image': // node_image finished
      var ns_status = 1;

      if (res.status == 'SUCCESS') {
        if (apiview.method == 'DELETE') { ns_status = null; } // remove row
      } else {
        if (apiview.method == 'POST') { break; } // no need to update the list
      }

      node_image_update(apiview.hostname, apiview.zpool, apiview.name, true, ns_status, 'ready');
      break;

    case 'node_sysinfo': // node_sysinfo refresh finished

      if (res.status == 'SUCCESS') {
        notify('success', gettext(result.message));
        if (node_refresh_page(hostname)) {
          return false; // do not update tasklog
        }
      } else {
        notify('error', _message_from_result(res));
      }
      break; // update cached tasklog

    case 'image_snapshot':
    case 'image_manage': // image_manage finished
      var remove = false;

      // Show message
      if (res.status == 'SUCCESS') {
        notify('success', gettext(result.message));
        if (apiview.method == 'DELETE') { remove = true; }
      } else {
        notify('error', _message_from_result(res));
        if (apiview.method == 'POST') { remove = true; }
      }

      // Update image list
      image_list_update(apiview.name, remove, apiview.status, apiview.status_display);

      if (apiview.view == 'image_snapshot') {
        // if there is a list of snapshots, then we need to update it
        vm_snapshots_update(hostname, null);
      }

      break; // always update cached tasklog
  }

  return true; // true => update cached_tasklog
}

// callback: "task_status"
function task_status_callback(res, apiview) {
  // Finished tasks with SUCCESS or FAILURE or REVOKED status
  if (_task_status_callback(res, apiview)) {
    // update cached_tasklog
    update_tasklog_cached();
  }
}
