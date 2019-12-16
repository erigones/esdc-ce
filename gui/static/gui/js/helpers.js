/************ HELPERS ************/
var LONG_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S %Z';
var SUBMENU_AUTO = true;
var SUBMENU_GAP = 0;
var ATIMEOUT = 120000;
var LOADING = null;
var MODAL = null;
var AJAX = null;
var NOTIFICATIONS = null;
var DATEINPUT_OPTIONS = {
  dateFormat: 'yy-mm-dd',
};
var FILEINPUT_OPTIONS = {
  autoUpload: false,
  maxFileSize: 5000000,
  replaceFileInput: false,  // This is required for our enviroment TODO: test old browsers
};
var ERIGONES_SUPPORTED_BROWSER = (function() {
  function _is_canvas_supported(){
    var elem = document.createElement('canvas');
    return !!(elem.getContext && elem.getContext('2d'));
  }

  function _is_style_supported(style){
    var elem = document.createElement('div');
    return style in elem.style;
  }

  return (
      'JSON' in window &&
      'sessionStorage' in window &&
      'WebSocket' in window && WebSocket.CLOSED > 2 &&
      _is_style_supported('opacity') &&
      _is_canvas_supported()
  );
})();

function is_value_in_field(field, value) {
  return Boolean(field.find('option[value="'+ value +'"]').length);
}

function get(obj, attr, default_value) {
  var val = obj[attr];

  if (val === undefined) {
    return default_value;
  }

  return val;
}

function pad(str, max) {
  return str.length < max ? pad('0' + str, max) : str;
}

function parse_bytes(val, unit) {
  val = val.toString();
  var matches = val.toUpperCase().match(/([0-9]+(\.[0-9]+)?)([BKMGTPE])/);

  if (matches) {
    var units = ['B', 'K', 'M', 'G', 'T', 'P', 'E'];
    var size = parseFloat(matches[1]);
    var res;

    if (unit == matches[3]) {
      res = size;
    } else {
      var pow = units.indexOf(matches[3]) - units.indexOf(unit.toUpperCase());
      res = size * Math.pow(1024, pow);
    }

    return Math.ceil(res).toString();
  }

  return val;
}

function toArray(str, sep, fun) {
  if (!str) {
    return [];
  }

  var a = String(str).split(sep);

  if (typeof(fun) !== 'undefined') {
    return _.map(a, fun);
  } else {
    return a;
  }
}

/*
 * Add or update query string parameter
 * Thanks to @niyazpk and @amorgner: https://gist.github.com/niyazpk/f8ac616f181f6042d1e0#gistcomment-1743025
 */
function update_query_string(uri, key, value) {
  // remove the hash part before operating on the uri
  var i = uri.indexOf('#');
  var hash = i === -1 ? '' : uri.substr(i);
      uri = i === -1 ? uri : uri.substr(0, i);

  var re = new RegExp("([?&])" + key + "=.*?(&|$)", "i");
  var separator = uri.indexOf('?') !== -1 ? "&" : "?";

  if (!value) {
    // remove key-value pair if value is empty
    uri = uri.replace(new RegExp("([?&]?)" + key + "=[^&]*", "i"), '');
    if (uri.slice(-1) === '?') {
      uri = uri.slice(0, -1);
    }
    // replace first occurrence of & by ? if no ? is present
    if (uri.indexOf('?') === -1) {
      uri = uri.replace(/&/, '?');
    }
  } else if (uri.match(re)) {
    uri = uri.replace(re, '$1' + key + "=" + value + '$2');
  } else {
    uri = uri + separator + key + "=" + value;
  }

  return uri + hash;
}

function parse_query_string(queryString) {
  var query = (queryString || window.location.search).substring(1); // delete ?

  if (!query) {
    return {};
  }

  return _.chain(query.split('&')).map(function(params) {
    var p = params.split('=');
    return [p[0], decodeURIComponent(p[1])];
  }).object().value();
}

function copy(oldObject) {
  return $.extend({}, oldObject);
}

function deepcopy(oldObject) {
  return $.extend(true, {}, oldObject);
}

function _jq(myid) {
  return myid.replace(/(:|\.|=)/g,'\\$1');
}
function jqi(myid) {
  return '#' + _jq(myid);
}

function jqc(myid) {
  return '.' + _jq(myid);
}

function jq(myid) {
  return jqi(myid);
}

function scroll_to_form_error(form_wrapper) {  /* Issue #35 */
  var first_error = form_wrapper.find('div.input.error:first');

  if (!first_error.length) {
    return;
  }

  var container_selector;
  var offset = first_error.offset().top - form_wrapper.offset().top;

  if ($('.profile-menu .profile-menu-nav-collapse').css('display') == 'none') { // Whether in mobile mode
    container_selector = '#main';
    offset += 40;
  } else {
    container_selector = 'html,body';
    offset += 180;
  }

  $(container_selector).animate({scrollTop: offset}, 500);
}

function scroll_to_modal_error(mod) {  /* Issue #12 */
  var first_error = mod.find('div.input.error:first');

  if (first_error.length) {
    first_error.get(0).scrollIntoView();
  }
}

function get_loading_screen(msg, dim, hide_close) {
  var backdrop;

  // Dim background?
  if ((typeof(dim) !== 'undefined') && (dim)) {
    backdrop = $('<div class="modal-backdrop"></div>');
  } else {
    backdrop = $('<div class="modal-backdrop-nodim"></div>');
  }

  // Copy the loading modal div, remove the hide class and attach to backdrop
  var loading = $('#loading').clone();

  if (msg) {
    loading.find('#loading_msg').html(msg);
  }

  loading.show().appendTo(backdrop);

  if ((typeof(hide_close) !== 'undefined') && (hide_close)) {
    backdrop.find('#loading-close').hide();
  } else {
    backdrop.find('#loading-close').click(ajax_abort);
  }

  return backdrop;
}

function hide_loading_screen() {
  if (LOADING) {
    LOADING.detach();
    LOADING = null;
  }
}

function show_loading_screen(msg, dim, hide_close) {
  hide_loading_screen();
  LOADING = get_loading_screen(msg, dim, hide_close);
  LOADING.appendTo(document.body);
  return LOADING;
}

function loading_button(btn, show) {
  if ((typeof(btn) !== 'undefined') && (btn.length)) {
    var i = btn.find('i');
    if (i.length) {
      if (show) {
        i.data('orig_class', i.attr('class')).attr('class', 'icon-cogs');
      } else {
        i.attr('class', i.data('orig_class'));
      }
    }
  }
}

function _ajax_error_message(xhr, textStatus, errorThrown) {
  var status = '???';

  if (xhr) {
    status = xhr.status;
  }

  if (!errorThrown) {
    errorThrown = gettext('Unknown error');
  }

  if (status === 0) {
    errorThrown = gettext('Network error') + ' (' + errorThrown + ')';
  }

  return textStatus +' '+ status  +': '+ errorThrown;
}

function ajax_error_handler(xhr, textStatus, errorThrown) {
  notify('error', _ajax_error_message(xhr, textStatus, errorThrown), 10);
}

function _ajax_before_send(btn, backdrop) {
  backdrop.appendTo(document.body);
  $('body').css('cursor', 'wait');
  loading_button(btn, true);
}

function _ajax_complete(btn, backdrop) {
  AJAX = null;
  backdrop.detach();
  $('body').css('cursor', 'auto');
  loading_button(btn, false);
}

function _ajax_success(success_handler, result, textStatus, xhr) {
  var new_url;

  switch (xhr.status) {
    case 281:
      console.log('Message', 'Incoming AJAX #main-body sub-page.');
      break;

    case 280:
      console.log('Message', 'Incoming AJAX #main-container sub-page.');
      break;

    case 279:
      // Classic redirect (redirect out of the authenticated section)
      // Remove QueryString (because it can contain ?next=<unwanted url>
      new_url = xhr.getResponseHeader('Location').split('?')[0];
      console.log('Message', 'Not authenticated. Classic redirect to:', new_url);
      window.location.replace(new_url);
      return false;

    case 278:
      // jQuery has a funny way of handling 302 redirects
      new_url = xhr.getResponseHeader('Location');
      console.log('Message', 'AJAX redirect detected. Move manually in success_handler using ajax_move to:', new_url);
      break;
  }

  return success_handler(result, textStatus, xhr);
}

function _ajax(datatype, method, url, timeout, success_handler, data, dim, btn) {
  if ((AJAX !== null) && (AJAX.readyState !== 4)) {
    return false;
  }

  var backdrop = get_loading_screen(null, dim);

  var kwargs = {
    type: method,
    url: url,
    dataType: datatype,
    timeout: timeout,
    error: ajax_error_handler,
    success: function(result, textStatus, xhr) {
      _ajax_success(success_handler, result, textStatus, xhr);
    },
    beforeSend: function(xhr, ajaxOptions) {
      _ajax_before_send(btn, backdrop);
    },
    complete: function(xhr) {
      _ajax_complete(btn, backdrop);
    }
  };

  if (typeof(data) !== 'undefined') {
    kwargs.data = data;
  }

  AJAX = $.ajax(kwargs);

  return AJAX;
}

function _ajax_file_upload(file_input, datatype, method, url, success_handler, data, dim, btn) {
  if ((AJAX !== null) && (AJAX.readyState !== 4)) {
    return false;
  }

  var backdrop = get_loading_screen(null, dim);
  var form_data = new FormData();

  if (typeof(data) !== 'undefined') {
    for (var i=0; i < data.length; i++) {
      form_data.append(data[i].name, data[i].value);
    }
  }

  file_input.slice(1).each(function(index, element) {
    for (var i=0; i < element.files.length; i++) {
      form_data.append($(this).attr('name'), element.files[i], element.files[i].name);
    }
  });

  var kwargs = {
    type: method,
    url: url,
    dataType: datatype,
    files: file_input[0].files,
    formData: form_data,
  };

  file_input.one('fileuploadsend', function() { _ajax_before_send(btn, backdrop); });

  AJAX = file_input.fileupload('send', kwargs)
    .error(function(jqXHR, textStatus, errorThrown) { ajax_error_handler(jqXHR, textStatus, errorThrown); })
    .complete(function (result, textStatus, jqXHR) { _ajax_complete(btn, backdrop); })
    .success(function(result, textStatus, jqXHR) { _ajax_success(success_handler, result, textStatus, jqXHR); });

  return AJAX;
}

function ajax(method, url, timeout, success_handler, data, dim, btn) {
  return _ajax('html', method, url, timeout, success_handler, data, dim, btn);
}

function ajax_json(method, url, timeout, success_handler, data, dim, btn) {
  return _ajax('json', method, url, timeout, success_handler, data, dim, btn);
}

function ajax_file(file_input, method, url, success_handler, data, dim, btn) {
  return _ajax_file_upload(file_input, 'html', method, url, success_handler, data, dim, btn);
}

function ajax_abort() {
  console.log('AJAX abort!');
  if (AJAX !== null) {
    return AJAX.abort();
  }
  return false;
}

function update_submenu(e) {
  var submenu = $('#sub-menu-list');
  if (submenu.length) {
    if (SUBMENU_AUTO && $('.profile-menu .profile-menu-nav-collapse').css('display') == 'none') {
      var tags_height = $('#vms_tags_wrapper').height() || 0;
      submenu.css('height', $(window).height() - SUBMENU_GAP - tags_height);
      var active = submenu.find('li.active');
      if (active.length) {
        active.get(0).scrollIntoView(true);
      }
    } else {
      submenu.css('height', 'auto');
    }
  }
}

function notify(lvl, msg, delay) {
  var iclass = '';
  var cls = '';

  if (NOTIFICATIONS === null) {
    NOTIFICATIONS = new NotificationBar();
  }

  if (typeof(delay) === 'undefined') {
    delay = 6;
  }

  switch (lvl) {
    case 'success':
      iclass = 'icon-ok-sign';
      break;
    case 'info':
      iclass = 'icon-info-sign';
      break;
    case 'error':
      iclass = 'icon-remove-sign';
      break;
    case 'warning':
      iclass = 'icon-warning-sign';
      break;
    default:
      cls = 'no-image';
      break;
  }

  NOTIFICATIONS.push({
    text: msg.replace(/\n/g, '<br />'),
    auto_dismiss: delay,
    main_class: cls,
    icon_class: iclass,
    image_class: 'img border',
  });
  $(window).scrollTop(0);
}

function enter_click(e) {
  if ((e.keyCode || e.which) == 13) {
    e.data.btn_enter.trigger('click');
  }
}

function disable_modal_form_enter(mod) {
  mod.off('keypress');
}

function enable_modal_form_enter(mod, mod_confirm_btn) {
  if (!mod_confirm_btn) {
    mod_confirm_btn = mod.find('a[data-enter="true"]:visible:last');
  }

  if ((mod_confirm_btn.length === 1) && !mod_confirm_btn.hasClass('disabled') && mod_confirm_btn.is(':visible')) {
    mod.on('keypress', {btn_enter: mod_confirm_btn}, enter_click);
  }
}

function activate_modal_ux(mod, mod_form, mod_confirm_btn) {
  disable_modal_form_enter(mod);

  mod.one('shown.bs.modal', function() {
    if (mod_form.length) {
      mod_form.find(':input:enabled:visible:first').focus();
    }

    enable_modal_form_enter(mod, mod_confirm_btn);
    return false;
  });
}

function _modal2(selector, text, header) {
  var self = this;
  this.mod = $(selector);
  this.mod_header = this.mod.find('span.modal2-header');
  this.mod_text = this.mod.find('p.modal2-text');
  this.mod_text.html(text);
  var mod_header_orig = this.mod_header.html();

  if (typeof(header) !== 'undefined') {
    this.mod_header.html(header);
  }

  this.mod.one('hidden', function() {
    self.mod_header.html(mod_header_orig);
    self.mod_text.html('');
    delete self.modal;
  });
}

function alert2(text, header) {
  var a = new _modal2('#alert2', text, header);

  activate_modal_ux(a.mod, $.noop);
  a.mod.modal('show');
}

function confirm2(text, cb_ok, cb_cancel, header) {
  var self = this;
  var a = new _modal2('#confirm2', text, header);

  var btn_ok = a.mod.find('a.confirm2-ok');
  var btn_cancel = a.mod.find('a.confirm2-cancel');

  if (typeof(cb_cancel) === 'undefined') {
    cb_cancel = $.noop;
  }

  a.mod.one('hide.modal', function() {
    btn_ok.off('click');
    btn_cancel.off('click');
  });

  btn_ok.on('click', function() { cb_ok(self); a.mod.modal('hide'); return false; });
  btn_cancel.on('click', function() { cb_cancel(self); a.mod.modal('hide'); return false; });

  activate_modal_ux(a.mod, $.noop);
  a.mod.modal('show');
}

function disable_form_submit(form) {
  if (form.length) {
    form.submit(function(e) {
      e.preventDefault();
      return false;
    });
  }
}

// Display modal window and run handler if OK button is clicked
function vm_modal(mod, btn, handler, handler_force, init) {
  if (typeof(handler_force) === 'undefined') {
    handler_force = function() { };
  }

  var self = this;
  var yes = mod.find('a.vm_modal_yes');
  var yes_default = yes.html();
  var no = mod.find('a.vm_modal_no');
  var no_default = no.html();
  var yes_force = mod.find('a.vm_modal_yes_force');
  var yes_force_default = yes_force.html();
  var title = mod.find('span.vm_modal_title');
  var title_default = title.html();
  var text = mod.find('.vm_modal_text');
  var text_default = text.html();
  var force = mod.find('.vm_modal_force_text');
  var force_default = force.html();

  this.form = mod.find('form');
  this.form_default = form.html();
  this.select = mod.find('select.input-select2');
  this.mod = mod;

  this.update_form = function(data) {
    self.form.html(data);
    self.select = $(self.select.selector);
    self.select.select2({dropdownCssClass: self.select.attr('class')});
    scroll_to_modal_error(mod);
  };

  var handler_data = {'modal': self};

  disable_form_submit(self.form);

  if (btn.data('modal_title')) {
    title.html(btn.data('modal_title'));
  }
  if (btn.data('modal_text')) {
    text.html(btn.data('modal_text'));
  }
  if (btn.data('modal_force_text')) {
    force.html(btn.data('modal_force_text'));
    yes_force.show();
    if (btn.data('modal_force_only')) {
      yes.hide();
    }
  } else {
    yes_force.hide();
  }
  if (btn.data('modal_no_text')) {
    no.html(btn.data('modal_no_text'));
  }
  if (btn.data('modal_yes_text')) {
    yes.html(btn.data('modal_yes_text'));
  }
  if (btn.data('modal_yes_force_text')) {
    yes_force.html(btn.data('modal_yes_force_text'));
  }

  mod.one('hide', function() {
    yes.off('click');
    yes_force.off('click');
    self.select.select2('destroy');
  });
  mod.one('hidden', function() {
    text.html(text_default);
    force.html(force_default);
    title.html(title_default);
    no.html(no_default);
    yes.html(yes_default);
    yes.show();
    yes_force.html(yes_force_default);
    yes_force.hide();
    if (self.form.length) {
      self.form.html(self.form_default);
      self.form[0].reset();
    }
  });

  if (btn.data('modal_nohide')) {
    yes.on('click', handler_data, handler);
    yes_force.on('click', handler_data, handler_force);
  } else {
    yes.one('click', function() {
      mod.modal('hide');
    });
    yes_force.one('click', function() {
      mod.modal('hide');
    });
    yes.one('click', handler_data, handler);
    yes_force.one('click', handler_data, handler_force);
  }

  self.select.select2({dropdownCssClass: self.select.attr('class')});
  activate_modal_ux(mod, form);

  if (typeof(init) !== 'undefined') {
    init(mod, form);
  }

  mod.modal('show');
  MODAL = mod;
}

function vm_modal_form_handler(e, handler) {
  var modal = e.data.modal;

  modal.form.find(':input').removeProp('disabled');

  ajax('POST', modal.form.data('source'), ATIMEOUT, function(data, textStatus, xhr) {
    if (xhr.status == 278) {
      if (typeof(handler) !== 'undefined') {
        handler(e);
      }
      modal.mod.modal('hide');
      ajax_move(null, xhr.getResponseHeader('Location'));
    } else if (xhr.status == 204) {
      modal.mod.modal('hide');
    } else {
      modal.update_form(data);
    }
  }, modal.form.serialize());

}

/*
 * Helper function used by mdata_input and array_input
 */
function _load_json_input(input_field, display_error) {
  var value_raw = input_field.val();

  if (value_raw) {
    try {
      return JSON.parse(value_raw);
    } catch (e) {
      if (display_error) {
        alert2(e.message);
      }
      return null;
    }
  } else {
    return {};
  }
}

/*
 * mdata_input functions
 */

function mdata_display(input_field) {
  if (!input_field.length) { return; }

  var control_group = input_field.parent();
  var row_template = _.template($('#template-mdata-row-inputs').html());
  var input_group = $('<div class="dynamic-input-group"></div>');
  var current_value = _load_json_input(input_field, false);

  control_group.children('div.dynamic-input-group').remove();

  if (current_value !== null) {
    // pretty print
    input_field.val(JSON.stringify(current_value, undefined, 4));
  }

  function hide_mdata_input() {
    var btn = $(this);
    input_field.off('focus', display_mdata_input);
    mdata_handler(input_field);  // This will show the original input field and update its value

    if (!btn.is(input_field)) {
      btn.remove();
    }

    input_group.detach();
    control_group.append($('#template-mdata-btn-enable').html());
    control_group.find('a.mdata-input-enable').click(display_mdata_input);
  }

  function display_mdata_input() {
    var btn = $(this);
    var row, input;
    var value = _load_json_input(input_field, true);

    if (value === null) {
      input_field.off('focus', display_mdata_input);
      return;
    }

    control_group.children('span.help-inline').hide();
    control_group.append(input_group);
    input_group.empty();
    input_field.hide();

    if (!btn.is(input_field)) {  // called from button instead of focus
      btn.remove();
    }

    $.each(value, function(key, val) {
      row = $(row_template({'key': key, 'value': val.replace(/\n/g, "\\n"), 'sign': 'minus icon-link-enabled'}));
      input_group.append(row);
      input = row.children().get(1);
      input.scrollLeft = input.scrollWidth;
    });

    input_group.append(row_template({'key': '', 'value': '', 'sign': 'plus icon-link-disabled'}));
    input_group.find('span.mdata-row:last input:first').focus();

    if (input_field.data('raw_input_enabled')) {
      control_group.append($('#template-mdata-btn-disable').html());
      control_group.find('a.mdata-input-disable').click(hide_mdata_input);
    }
  }

  input_field.focus(display_mdata_input);

  input_group.on('click', 'span.icon-minus', function() {
    $(this).parent().remove();
  });

  input_group.on('click', 'span.icon-plus.icon-link-enabled', function() {
    $(this).removeClass('icon-plus').addClass('icon-minus');
    input_group.append(row_template({'key': '', 'value': '', 'sign': 'plus icon-link-disabled'}));
  });

  input_group.on('keyup', 'input.mdata-key', function() {
    var input_key = $(this);
    if (input_key.val()) {
      input_key.parent().find('span.icon-plus.icon-link-disabled').removeClass('icon-link-disabled').addClass('icon-link-enabled');
    } else {
      input_key.parent().find('span.icon-plus.icon-link-enabled').removeClass('icon-link-enabled').addClass('icon-link-disabled');
    }
  });
}

function mdata_handler(input_field) {
  if (!input_field.length) { return; }

  var input_group = input_field.parent().find('div.dynamic-input-group');
  var rows = input_group.children('span.mdata-row');

  // do not bother if there are no mdata-rows around
  if (rows.length) {
    // glue together JSON for mdata
    var result = {};

    $.each(rows, function() {
      var children = this.children;
      if (children[0].value || children[1].value) {
        result[children[0].value] = children[1].value;
      }
    });

    // Update textarea and clean mdata-rows
    rows.remove();
    input_field.val(JSON.stringify(result, undefined, 4).replace(/\\\\n/g, "\\n"));
    input_field.show();
  }
}

function mdata_enable(fields) {
  $.each(fields, function() {
    mdata_display($(this));
  });
}

function mdata_prepare(fields) {
  $.each(fields, function() {
    mdata_handler($(this));
  });
}


/*
 * array_input functions
 */

function array_display(input_field) {
  if (!input_field.length) { return; }

  var control_group = input_field.parent();
  var row_template = _.template($('#template-array-row-inputs').html());
  var input_group = $('<div class="dynamic-input-group"></div>');
  var current_value = _load_json_input(input_field, false);

  control_group.children('div.dynamic-input-group').remove();

  if (current_value !== null) {
    // pretty print
    input_field.val(JSON.stringify(current_value, undefined, 4));
  }

  function display_array_input() {
    var btn = $(this);
    var row, input;
    var value = _load_json_input(input_field, true);

    if (value === null) {
      input_field.off('focus', display_array_input);
      return;
    }

    control_group.children('span.help-inline').hide();
    control_group.append(input_group);
    input_group.empty();
    input_field.hide();

    if (!btn.is(input_field)) {  // called from button instead of focus
      btn.remove();
    }

    $.each(value, function(i, val) {
      row = $(row_template({'value': val, 'sign': 'minus icon-link-enabled'}));
      input_group.append(row);
      input = row.children().get(0);
      input.scrollLeft = input.scrollWidth;
    });

    input_group.append(row_template({'value': '', 'sign': 'plus icon-link-disabled'}));
    input_group.find('span.array-row:last input:first').focus();
  }

  input_field.focus(display_array_input);

  input_group.on('click', 'span.icon-minus', function() {
    $(this).parent().remove();
  });

  input_group.on('click', 'span.icon-plus.icon-link-enabled', function() {
    $(this).removeClass('icon-plus').addClass('icon-minus');
    input_group.append(row_template({'value': '', 'sign': 'plus icon-link-disabled'}));
  });

  input_group.on('keyup', 'input.array-val', function() {
    var input_val = $(this);
    if (input_val.val()) {
      input_val.parent().find('span.icon-plus.icon-link-disabled').removeClass('icon-link-disabled').addClass('icon-link-enabled');
    } else {
      input_val.parent().find('span.icon-plus.icon-link-enabled').removeClass('icon-link-enabled').addClass('icon-link-disabled');
    }
  });
}

function array_handler(input_field) {
  if (!input_field.length) { return; }

  var input_group = input_field.parent().find('div.dynamic-input-group');
  var rows = input_group.children('span.array-row');

  // do not bother if there are no array-rows around
  if (rows.length) {
    // glue together JSON for full array
    var result = [];

    $.each(rows, function() {
      var children = this.children;
      if (children[0].value) {
        result.push(children[0].value);
      }
    });

    // Update textarea and clean array-rows
    rows.remove();
    input_field.val(JSON.stringify(result));
    input_field.show();
  }
}

function array_enable(fields) {
  $.each(fields, function() {
    array_display($(this));
  });
}

function array_prepare(fields) {
  $.each(fields, function() {
    array_handler($(this));
  });
}


/*
 * Megabyte input helper
 */
function mbytes_handler(input_field) {
  input_field.on('keyup', function() {
    var f = $(this);

    f.val(parse_bytes(f.val(), 'M'));
  });
}

function mbytes_enable(fields) {
  $.each(fields, function() {
    mbytes_handler($(this));
  });
}



/*
 * Browser hacks and usability improvements
 */

function validate_html_form(form) {
  if (!form.length) {
    return null;
  }

  // Fake HTML 5 validation
  $('<input type="submit">').hide().appendTo(form).click().remove();

  return form[0].checkValidity();
}

function is_touch_device() {
  return (!!('ontouchstart' in window) || !!('onmsgesturechange' in window));
}

function activate_tooltips() {
  if (!is_touch_device()) {
    $('#main-body').tooltip({
      selector: "a[data-toggle=tooltip], span[data-toggle=tooltip], input[data-toggle=tooltip], span.input-error"
    });
  }
}

function activate_nav_collapse() {
  $('.profile-menu-nav-collapse .button').click(function(e) {
    $('.secondary-nav-menu').toggleClass('open');
  });
}

function activate_morerow() {
  $('a.morerow-toggle').click(function() {
    var btn = $(this);
    var i = btn.find('i');
    $('div.morerow').slideToggle();

    if (i.hasClass('icon-caret-down')) {
      i.attr('class', 'icon-caret-up');
    } else {
      i.attr('class', 'icon-caret-down');
    }

    return false;
  });
}

function check_browser_support() {
  if (!ERIGONES_SUPPORTED_BROWSER) {
    $('#not_supported_browser').show();
  }
}

$(document).ready(function() {
  $("html, body").off("touchstart");
  check_browser_support();
  activate_tooltips();
});
