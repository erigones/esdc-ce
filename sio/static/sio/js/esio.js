var SOCKET = io.connect(SOCKETIO_URL, {
    'sync disconnect on unload': false,
});

SOCKET.on("message", function(caller, method, scode, result, args, kwargs, apiview, apidata) {
  console.log("Message", scode, result, caller, method, args, kwargs, apiview, apidata);
  message_callback(scode, result, caller, method, args, kwargs, apiview, apidata);
});

SOCKET.on("task_status", function(result, apiview) {
  console.log("Task status", result, apiview);
  task_status_callback(result, apiview);
});

SOCKET.on("task_event", function(result) {
  console.log("Task event", result);
  task_event_callback(result);
});

SOCKET.on("info", function(sender, args, kwargs) {
  console.log("Info", sender, args, kwargs);
  info_callback(sender, args, kwargs);
});

SOCKET.on("error", function(error_name, error_message) {
  console.log("Error", error_name, error_message);
  error_callback(error_name, error_message);
});

SOCKET.on("connect", function(e) {
  console.log("Connected");
  connect_callback(e);
  SOCKET.emit('subscribe');
});

SOCKET.on("disconnect", function(e) {
  console.log("Disconnected");
  disconnect_callback(e);
});

SOCKET.on("unsubscribe", function(e) {
  console.log("Unsubscribe");
});

function esio(action, view, args, kwargs) {
  if (!SOCKET.socket.connected) {
    alert2(gettext('Socket.io disconnected. Cannot execute task.'));
    return false;
  }

  var method = {
    'get'   : 'GET',
    'create': 'POST',
    'set'   : 'PUT',
    'delete': 'DELETE',
    'GET'   : 'GET',
    'POST'  : 'POST',
    'PUT'   : 'PUT',
    'DELETE': 'DELETE',
  };

  var _view = view.split('_');
  var module = _view[0];

  if (typeof(args) === 'undefined') {
    args = [];
  }

  if (typeof(kwargs) === 'undefined') {
    kwargs = {};
  }

  return SOCKET.emit(module, method[action], view, args, kwargs);
}

function get_siosid() {
  return SOCKET.socket.sessionid || '';
}
