function GuacamoleErigones(guac, zoom_enabled) {

  var self = this;
  var guac_display = guac.getDisplay();
  var guac_element = guac_display.getElement();
  var display = document.getElementById('display');
  var message = document.getElementById('message');
  var onscreen_keyboard = document.getElementById('onscreen-keyboard');
  var onscreen_keyboard_source = onscreen_keyboard.getAttribute('data-source');
  var onscreen_keyboard_enabled = false;
  var onscreen_keyboard_downloading = false;
  var touch_keyboard = document.getElementById('touch-keyboard');
  var touch_keyboard_enabled = false;
  var mouse = null;
  var keyboard = null;
  var keyboard2 = null;
  var keyboard_status = 0;
  var connection = null;
  var menu = {
    'menu': document.getElementById('menu'),
    'btn_capture': document.getElementById('btn-capture'),
    'btn_zoom': document.getElementById('btn-zoom'),
    'btn_kbd': document.getElementById('btn-kbd'),
    'btn_menu': document.getElementById('btn-menu'),
  };
  var KEYSYM_CTRL = 65507;
  var KEYSYM_ALT = 65513;
  var KEYSYM_DELETE = 65535;

  if (typeof(zoom_enabled) === 'undefined') {
    zoom_enabled = false;
  }

  // Connect
  this.connect = function (data) {
    guac.connect(data);
  };

  // Hide message
  this.hide_message = function () {
    message.className = 'hide';
    display.className = '';
  };

  // Show message
  this.show_message = function (text) {
    message.innerHTML = text;
    display.className = 'disabled';
    message.className = '';
  };

  // Touch keyboard
  this.toggle_touch_keyboard = function (show) {
    touch_keyboard_enabled = show;

    if (touch_keyboard_enabled) {
      touch_keyboard.className = '';
      touch_keyboard.focus();
    } else {
      touch_keyboard.blur();
      touch_keyboard.className = 'hide';
    }
  };

  this.resize_touch_keyboard = function () {
    // Hide native keyboard on every resize
    if (keyboard_status == 3) {
      self.toggle_touch_keyboard(false);
      keyboard_status = 0;
    }
  };

  // OnScreen keyboard
  this.resize_onscreen_keyboard = function () {
    if (keyboard2 && onscreen_keyboard_enabled) {

      if (onscreen_keyboard_enabled == 'full') {
        onscreen_keyboard.style.top = guac_element.offsetHeight + 1 + 'px';

      } else if (onscreen_keyboard_enabled == 'compact') {
        onscreen_keyboard.style.top = 'auto';
      }

      if (keyboard2.width != onscreen_keyboard.offsetWidth) {
        keyboard2.resize(onscreen_keyboard.offsetWidth);
      }

    }
  };

  init_onscreen_keyboard = function (show_keyboard_handler) {
    if (!onscreen_keyboard_source || onscreen_keyboard_downloading) {
      return false;
    }

    onscreen_keyboard_downloading = true;

    var xhr = new XMLHttpRequest();
    var layout;

    xhr.onreadystatechange = function () {
      if (xhr.readyState == XMLHttpRequest.DONE) {
        if (xhr.status == 200 || xhr.status == 304) {
          layout = JSON.parse(xhr.responseText);
          keyboard2 = new Guacamole.OnScreenKeyboard(layout);
          onscreen_keyboard.appendChild(keyboard2.getElement());

          keyboard2.onkeydown = function (keysym) {
            guac.sendKeyEvent(1, keysym);
          };
          keyboard2.onkeyup = function (keysym) {
            guac.sendKeyEvent(0, keysym);
          };

          var cads = document.getElementsByClassName('guac-keyboard-key-ctrl-alt-del');
          if (cads.length) {
            cads[0].onclick = ctrl_alt_delete_keystroke;
          }

          show_keyboard_handler();

        }
        onscreen_keyboard_downloading = false;
      }
    };

    xhr.open('GET', onscreen_keyboard_source, true);
    xhr.send();
  };

  function _enable_onscreen_keyboard() {
    onscreen_keyboard.className = onscreen_keyboard_enabled;
    self.resize_onscreen_keyboard();
  }

  function enable_onscreen_keyboard() {
    if (keyboard2 === null) {
      init_onscreen_keyboard(_enable_onscreen_keyboard);
    } else {
      _enable_onscreen_keyboard();
    }
  }

  function disable_onscreen_keyboard() {
    onscreen_keyboard.className = 'hide';
  }

  function ctrl_alt_delete_keystroke(e) {
    e.preventDefault();
    guac.sendKeyEvent(1, KEYSYM_CTRL);
    guac.sendKeyEvent(1, KEYSYM_ALT);
    guac.sendKeyEvent(1, KEYSYM_DELETE);

    guac.sendKeyEvent(0, KEYSYM_DELETE);
    guac.sendKeyEvent(0, KEYSYM_ALT);
    guac.sendKeyEvent(0, KEYSYM_CTRL);
    return false;
  }

  this.toggle_onscreen_keyboard = function (cls) {
    onscreen_keyboard_enabled = cls;

    if (onscreen_keyboard_enabled) {
      enable_onscreen_keyboard();
    } else {
      disable_onscreen_keyboard();
    }
  };

  // Zoom
  this.zoom = function (yes) {
    if (typeof(yes) !== 'undefined') {
      zoom_enabled = yes;
    }

    if (zoom_enabled) {
      var scale = Math.min(window.innerWidth / guac_display.getWidth(),
        window.innerHeight / guac_display.getHeight());

      if (scale != guac_display.getScale()) {
        guac_display.scale(scale);
      }

    } else if (guac_display.getScale() != 1.0) {
      guac_display.scale(1.0);
    }

    self.resize_onscreen_keyboard();
  };


  /*        *
   *  INIT  *
   *        */

  // Add client to display div
  guac_element.className = 'guac_display';
  display.appendChild(guac_element);

  // State change
  guac.onstatechange = function (state) {
    switch (state) {
      case 0:
        self.show_message(gettext('Idle.'));
        break;
      case 1:
        self.show_message(gettext('Connecting...'));
        break;
      case 2:
        self.show_message(gettext('Connected, waiting for first update...'));
        break;
      case 3:
        self.hide_message(); // Connected
        break;
      case 4:
        self.show_message(gettext('Disconnecting...'));
        break;
      case 5:
        self.show_message(gettext('Disconnected.'));
        break;
      default:
        self.show_message(gettext('Unknown status'));
        break;
    }
  };

  // Name change
  guac.onname = function (name) {
    connection = name;
  };

  // Errors
  guac.onerror = function (error) {
    self.show_message(error);
    guac.disconnect();
  };

  // Resize
  guac.onresize = function (width, height) {
    self.zoom();
  };

  // Disable default click action
  guac_element.onclick = function (e) {
    e.preventDefault();
    return false;
  };

  // Mouse / Touch
  mouse = new Guacamole.Mouse(guac_element);
  touch = new Guacamole.Mouse.Touchpad(guac_element);

  touch.onmousedown = touch.onmouseup = touch.onmousemove =
    mouse.onmousedown = mouse.onmouseup = mouse.onmousemove = function (ms) {
      var mss = new Guacamole.Mouse.State(
        ms.x / guac_display.getScale(),
        ms.y / guac_display.getScale(),
        ms.left, ms.middle, ms.right, ms.up, ms.down);
      guac.sendMouseState(mss);
    };

  // Keyboard
  keyboard = new Guacamole.Keyboard(document);

  keyboard.onkeydown = function (keysym) {
    guac.sendKeyEvent(1, keysym);
  };
  keyboard.onkeyup = function (keysym) {
    guac.sendKeyEvent(0, keysym);
  };

  // Disconnect
  window.onunload = function () {
    guac.disconnect();
  };

  window.onresize = function () {
    guac.sendSize(window.innerWidth, window.innerHeight);
    self.zoom();
  };


  /*        *
   *  MENU  *
   *        */

  // Focus on display
  menu.btn_capture.onclick = function (e) {
    guac.sendKeyEvent(1, 'z');
    guac.sendKeyEvent(0, 'z');
    self.resize_touch_keyboard();
    display.focus();
  };

  // Switch zoom setting
  menu.btn_zoom.onclick = function (e) {
    self.zoom(!zoom_enabled);

    if (zoom_enabled) {
      menu.btn_zoom.innerHTML = '<i class="icon-resize-small"></i>';
    } else {
      menu.btn_zoom.innerHTML = '<i class="icon-resize-full"></i>';
    }
  };

  // Show / Hide touchscreen keyboard
  menu.btn_kbd.onclick = function (e) {
    switch (keyboard_status) {
      case 0:
        self.toggle_onscreen_keyboard('compact');
        self.toggle_touch_keyboard(false);
        keyboard_status = 1;
        menu.btn_kbd.innerHTML = '<i class="icon-hand-down"></i>';
        break;
      case 1:
        self.toggle_onscreen_keyboard('full');
        self.toggle_touch_keyboard(false);
        keyboard_status = 3; // Touch keyboard is disabled
        menu.btn_kbd.innerHTML = '<i class="icon-hand-up"></i>';
        break;
      case 2:
        self.toggle_onscreen_keyboard(false);
        self.toggle_touch_keyboard(true);
        keyboard_status = 3;
        menu.btn_kbd.innerHTML = '<i class="icon-hand-up"></i>';
        break;
      default:
        self.toggle_onscreen_keyboard(false);
        self.toggle_touch_keyboard(false);
        keyboard_status = 0;
        menu.btn_kbd.innerHTML = '<i class="icon-text-height"></i>';
        break;
    }
  };

  // Change menu position
  menu.btn_menu.onclick = function (e) {
    switch (menu.menu.className) {
      case 'right':
        menu.menu.className = 'bottom';
        break;
      case 'bottom':
        menu.menu.className = 'left';
        break;
      case 'left':
        menu.menu.className = 'top';
        break;
      default:
        menu.menu.className = 'right';
        break;
    }
  };

} // GuacamoleErigones
