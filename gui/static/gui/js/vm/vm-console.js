/************ VNC CONTROL ************/
function VNC(vnc_window, vnc_window_height) {
  var self = this;
  var loaded = false;
  var loading = false;

  if (typeof(vnc_window_height) === 'undefined') {
    vnc_window_height = null;
  }

  this.update_vnc_iframe = function() {
    if (!vnc_window.length) {
      return;
    }

    var win_height;
    var win_width_e = vnc_window.parent(); // just get the element, because we need to set the width twice (scrollbar problem)

    if (vnc_window_height === null) {
      win_height = $(window).height() - 120;
    } else {
      win_height = vnc_window_height;
    }

    vnc_window.width(win_width_e.outerWidth() - 1);
    vnc_window.height(win_height);
    vnc_window.width(win_width_e.outerWidth() - 1);
  };

  this.focus_vnc = function() {
    if (vnc_window.length) {
      vnc_window[0].contentWindow.focus();
    }
  };

  this.is_loading = function() {
    return loading;
  };

  this.is_loaded = function() {
    return loaded;
  };

  this.load = function() {
    if (!vnc_window.length) {
      return;
    }

    if (loaded || loading) {
      return false;
    }

    loading = true;
    self.update_vnc_iframe();

    var win = $(window);
    win.bind('resize', self.update_vnc_iframe);
    win.bind('orientationchange', self.update_vnc_iframe);

    vnc_window.load(function() {
      self.update_vnc_iframe();
      self.focus_vnc();
      loading = false;
      loaded = true;
    });
  };

  self.load();
} // VNC


// Reload a console window if server status changed to running
function vm_vnc_update(hostname, status_display) {
  if (status_display == 'running') {
    var vnc_window = $(jq('vnc_' + hostname));

    if (vnc_window.length) {
      vnc_window.attr('src', vnc_window.attr('src'));
    }
  }
}
