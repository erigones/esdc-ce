var SYSTEM_UPDATE = null;
var SYSTEM_UPDATE_LOADING = null;

function SystemUpdate() {
  var self = this;
  var modal = null;

  function hide_system_update_loading_screen() {
    if (SYSTEM_UPDATE_LOADING) {
      SYSTEM_UPDATE_LOADING.detach();
      SYSTEM_UPDATE_LOADING = null;
    }
  }

  function show_system_update_loading_screen() {
    SYSTEM_UPDATE_LOADING = get_loading_screen('Update in progress (please wait)', true, true);
    SYSTEM_UPDATE_LOADING.appendTo(document.body);
  }

  this.is_displayed = function() {
    return Boolean($('#update_modal').length);
  };

  this.started = function(e) {
    // Hide previous update loading screen
    hide_system_update_loading_screen();
    // Hide other loading screens
    hide_loading_screen();
    // Show update loading screen
    show_system_update_loading_screen();
    // Hide modal if displayed
    if (self.modal) {
      self.modal.mod.modal('hide');
    }
  };

  this.finished = function(e) {
    // Hide other loading screens
    hide_loading_screen();
    // Hide update loading screen
    hide_system_update_loading_screen();
  };

  /******** START *********/
  NODE_LIST = new NodeList({});
  SOCKET.emit('check_system_lock');

  $('#system_update').click(function() {
   	self.modal = new obj_form_modal($(this), '#update_modal');

    return false;
  });

  $('#node_system_update').click(function() {
    self.modal = new obj_form_modal($(this), '#node_update_modal', function(mod, start) {
      if (start) {
        var hostnames = NODE_LIST.get_hostnames();
        $('#id_node-hostnames_text').html(hostnames.join(', '));
        $('#id_node-hostnames').val(hostnames);
      }
    });

    return false;
  });
} // SystemUpdate
