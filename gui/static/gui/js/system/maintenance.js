var SYSTEM_VERSION_URL = 'https://danubecloud.org/api/releases';
var SYSTEM_UPDATE = null;
var SYSTEM_UPDATE_LOADING = null;
var SYSTEM_UPDATE_RESTART_DELAY = 10;

function get_available_system_versions(handler) {
  ajax_json('GET', SYSTEM_VERSION_URL + '?system_version=' + SYSTEM_VERSION, ATIMEOUT, handler);
}

function get_latest_system_version(handler) {
  get_available_system_versions(function(data) {
    handler(data[0]);
  });
}

function hide_system_update_loading_screen() {
  if (SYSTEM_UPDATE_LOADING) {
    SYSTEM_UPDATE_LOADING.detach();
    SYSTEM_UPDATE_LOADING = null;
  }
}

function show_system_update_loading_screen() {
  SYSTEM_UPDATE_LOADING = get_loading_screen('System update in progress (please wait)', true, true);
  SYSTEM_UPDATE_LOADING.appendTo(document.body);
}

function _system_update_started() {
  // Hide previous update loading screen
  hide_system_update_loading_screen();
  // Hide other loading screens
  hide_loading_screen();
  // Show update loading screen
  show_system_update_loading_screen();
}

function _system_update_finished() {
  // Hide other loading screens
  hide_loading_screen();
  // Hide update loading screen
  hide_system_update_loading_screen();
}

// Run after we get a broadcast event
function system_update_started() {
  SYSTEM_UPDATE_RUNNING = true;
  _system_update_started();
}

// Run after we get a broadcast event
function system_update_finished(error) {
  SYSTEM_UPDATE_RUNNING = false;

  if (error) {
    _system_update_finished();
  } else {
    // A complete system restart will follow in 10 seconds
    setTimeout(function() {
      _system_update_finished();
      alert2(gettext('The system was restarted. Please refresh your browser.'));
    }, SYSTEM_UPDATE_RESTART_DELAY * 1000);
  }
}

// Always run at each page load
function system_update_check() {
  if (SYSTEM_UPDATE_RUNNING) {
    _system_update_started();
  }
}

// Update node version span
function node_system_version_update(hostname, version) {
  var version_span = $(jq('node_system_version_' + hostname)); // escaping dots in hostname

  if (!version_span.length) {
    return;
  }

  version_span.text(version);
}

// Update system version span
function system_version_update(version) {
  var version_span = $(jq('system_version'));

  if (!version_span.length) {
    return;
  }

  version_span.text(version);
}

function SystemUpdate() {
  var self = this;
  var modal = null;

  this.is_displayed = function() {
    return Boolean($('#system_update_modal').length);
  };

  this.started = function(hostname) {
    // Hide modal if displayed
    if (self.modal) {
      self.modal.mod.modal('hide');
    }
  };

  this.finished = function(hostname, error) {
    // Notify user
    if (error) {
      if (hostname) {
        notify('error', interpolate(gettext('System update on node %s failed (see task log in the main DC)'), [hostname]));
      } else {
        notify('error', gettext('System update failed (see task log in the main DC)'));
      }
    } else {
      if (hostname) {
        notify('success', interpolate(gettext('System update on node %s successfully finished<br>(Please wait for the node software to be restarted)'), [hostname]));
        node_system_version_update(hostname, '...');
      } else {
        notify('success', gettext('System update successfully finished<br>(Please wait for the system software to be restarted)'));
        system_version_update('...');
      }
    }
  };

  function enable_latest_system_version_btn() {
    $('a.latest_system_version').click(function() {
      var btn = $(this);

      get_latest_system_version(function(data) {
        if (data.name) {
          btn.prev().val(data.name);
        }
      });

      return false;
    });
  }

  /******** START *********/
  NODE_LIST = new NodeList({});

  $('#system_update').click(function() {
    self.modal = new obj_form_modal($(this), '#system_update_modal', function(mod, start) {
      enable_latest_system_version_btn();
    });

    return false;
  });

  $('#node_system_update').click(function() {
    self.modal = new obj_form_modal($(this), '#node_update_modal', function(mod, start) {
      if (start) {
        var hostnames = NODE_LIST.get_hostnames();
        $('#id_node-hostnames_text').html(hostnames.join(', '));
        $('#id_node-hostnames').val(hostnames);
      }
      enable_latest_system_version_btn();
    });

    return false;
  });
} // SystemUpdate

