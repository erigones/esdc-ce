/* jshint -W030 */

function default_table_obj_postfun() {
  $(this).removeClass('info error');
}

function table_obj_added(tr, postfun) {
  tr.addClass('info').fadeTo(300, 0.3).fadeTo(2000, 1.0, postfun || default_table_obj_postfun);
}

function table_obj_removed(tr, postfun) {
  tr.addClass('error').fadeTo(300, 0.3).fadeTo(300, 1.0).fadeTo(1800, 0.1, postfun || default_table_obj_postfun);
}

function table_obj_updated(tr, postfun) {
  tr.addClass('info').fadeTo(300, 0.3).fadeTo(300, 1.0).fadeTo(300, 0.3).fadeTo(300, 1.0, postfun || default_table_obj_postfun);
}

function update_form_fields(form, form_data, prefix) {
  if (form_data) {

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
        if (value === null) {
          value = '';
        } else if ($.isArray(value)) {
          if (field.hasClass('input-array')) {
            value = JSON.stringify(value, undefined, 4);
          } else if (!field.attr('multiple')) {
            value = value.join(',');
          }
        } else if ($.isPlainObject(value)) {
          value = JSON.stringify(value, undefined, 4);
        }

        field.val(value);
        field.attr('placeholder', value);

        if (field.hasClass('input-select2')) {
          field.select2('val', value);
        }
      }
    });

    return true;
  }

  return false;
}

/****************
 * obj_form_modal
 */
function obj_form_modal(btn, mod_selector, init, handler) {
  if (btn.hasClass('disabled')) {
    return false;
  }

  var self = this;
  var mod = $(mod_selector);
  var add = btn.hasClass('obj_add');
  var form_data = btn.data('form') || null;
  var form = mod.find('form');
  var form_default = form.html();
  var btn_update = mod.find('a.vm_modal_update');
  var btn_delete = mod.find('a.vm_modal_delete');
  var btn_create = mod.find('a.vm_modal_create');
  var btn_more = mod.find('a.vm_modal_more');
  var title_edit = mod.find('span.title_edit');
  var title_add = mod.find('span.title_add');
  var text_edit = mod.find('div.text_edit');
  var text_add = mod.find('div.text_add');
  var text_default;
  var select = mod.find('select.input-select2');
  var select_tags = mod.find('input.tags-select2');
  var dateinput = mod.find('.input-date');
  var fileinput = mod.find('input:file');
  var mdata_input = mod.find('textarea.input-mdata');
  var array_input = mod.find('textarea.input-array');

  this.mod = mod;
  this.btn = btn;
  this.add = add;
  this.btn_more = btn_more;
  this.form = form;
  this.form_data = form_data;

  disable_form_submit(form);

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

  if (typeof(handler) === 'undefined') {  // we need default handler
    var ajax_handler = function(data, textStatus, xhr) {
      switch (xhr.status) {
        case 204:
          mod.modal('hide');
          break;

        case 278:
          mod.modal('hide');
          ajax_move(null, xhr.getResponseHeader('Location'));
          break;

        case 280:
          $('#main-body').html(data);
          mod.modal('hide');
          break;

        case 281:
          $('#main-container').html(data);
          mod.modal('hide');
          break;

        default:
          form.html(data);
          select = $(select.selector);
          select_tags = $(select_tags.selector);
          dateinput = $(dateinput.selector);
          fileinput = $(fileinput.selector);
          mdata_input = $(mdata_input.selector);
          array_input = $(array_input.selector);
          vm_forms_toggle(add, mod);
          init(self, false);
          select.select2({dropdownCssClass: select.attr('class')});
          select_tags.each(function() { $(this).select2({tags: $(this).data('tags') || [], dropdownCssClass: $(this).attr('class'), tokenSeparators: [',', ' ']}); });
          dateinput.datepicker(DATEINPUT_OPTIONS);
          fileinput.fileupload(FILEINPUT_OPTIONS);
          mdata_enable(mdata_input);
          array_enable(array_input);

          if (mod.find('div.advanced div.input.error').length || btn_more.hasClass('active')) {
            morehandler(true);
          }

          scroll_to_modal_error(mod);
          break;
      }
    };

    handler = function(e) {
      var action_btn = $(this);
      if (action_btn.hasClass('disabled')) {
        return false;
      }

      mdata_prepare(mdata_input);
      array_prepare(array_input);

      form.find(':input').removeProp('disabled');

      var url = action_btn.data('source') || form.data('source');
      var data = form.serializeArray();

      data.push({name: 'action', value: e.data.action});
      data.push({name: 'siosid', value: get_siosid()});

      if (fileinput.length && fileinput[0].files.length) {
        ajax_file(fileinput, form.attr('method'), url, ajax_handler, data);
      } else {
        ajax(form.attr('method'), url, ATIMEOUT, ajax_handler, $.param(data));
      }
    };

  }  // default handler

  if (add) {
    title_add.show();
    title_edit.hide();
    text_add.show();
    text_edit.hide();
    self.text = text_add;
    btn_update.length && btn_update.hide();
    btn_delete.length && btn_delete.hide();
    btn_create.length && btn_create.show();
    vm_forms_toggle(true, mod);

  } else {
    title_add.hide();
    title_edit.show();
    text_add.hide();
    text_edit.show();
    self.text = text_edit;
    btn_update.length && btn_update.show();
    btn_delete.length && btn_delete.show().removeClass('disabled');
    btn_create.length && btn_create.hide();
    vm_forms_toggle(false, mod);

    if (btn.hasClass('no-delete')) {
      btn_delete.length && btn_delete.addClass('disabled');
    }
  }

  text_default = self.text.html();

  update_form_fields(form, form_data, btn.data('prefix'));

  mod.one('hide', function() {
    btn_update.length && btn_update.off('click');
    btn_delete.length && btn_delete.off('click');
    btn_create.length && btn_create.off('click');
    if (btn_more.length) { btn_more.off('click'); morehandler(false); }
    select.select2('destroy');
    select_tags.select2('destroy');
    dateinput.datepicker('destroy');
    fileinput.fileupload('destroy');
  });

  mod.one('hidden', function() {
    if (form.length) {
      form.html(form_default);
      form[0].reset();
    }
    self.text.html(text_default);
  });

  btn_update.length && btn_update.on('click', {action: 'update'}, handler);
  btn_delete.length && btn_delete.on('click', {action: 'delete'}, handler);
  btn_create.length && btn_create.on('click', {action: 'create'}, handler);
  btn_more.length && btn_more.on('click', morehandler);

  if (typeof(init) !== 'undefined') {
    init(self, true);
  } else {
    init = $.noop;
  }

  select.select2({dropdownCssClass: select.attr('class')});
  select_tags.each(function() { $(this).select2({tags: $(this).data('tags') || [], dropdownCssClass: $(this).attr('class'), tokenSeparators: [',', ' ']}); });
  dateinput.datepicker(DATEINPUT_OPTIONS);
  fileinput.fileupload(FILEINPUT_OPTIONS);
  mdata_enable(mdata_input);
  array_enable(array_input);
  activate_modal_ux(mod, form);
  mod.modal('show');
} // dc_form_modal


/***********
 * CheckList
 */
function CheckList() {
  var self = this;
  this.enabled = true;
  this.selected = {};
  this.elements = {
    'chbox_all':    $('#id_all'),
    'chbox_tr':     $('#etable tbody input[type="checkbox"]:enabled'),
    'tbody_tr':     $('#etable tbody tr'),
    'tfoot':        $('#etable tfoot'),
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

  // Override this method if you need to do something special when selected object changes
  this.selected_changed = $.noop;

  // Update tfoot selected count and run callback
  this.toggle = function() {
    var count;

    if ($.isEmptyObject(self.selected)) {
      count = 0;
    } else {
      count = _.size(self.selected);
    }

    self.elements.selected.html(count);
    self.selected_changed(count);
  };

  // New table check operation
  this.reset = function() {
    self.selected = {};
    self.elements.chbox_all.prop('checked', false);
    self.elements.chbox_tr.prop('checked', false);
    self.elements.tbody_tr.removeClass('highlight');
    self.toggle();
  };

  // **** START ****
  this.reset();

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

    self.toggle();

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

    self.toggle();

    return true;
  });

} // CheckList


/*********
 * obj_list_sort_js
 */
function obj_list_sort_js(table, nosort, custsort) {
  if (typeof(nosort) === 'undefined') {
    nosort = [-1];
  }

  var order_by_default = null;
  var column_defs = [
    {'bSortable': false, 'aTargets': nosort},
    {'bSearchable': false, 'aTargets': nosort},
  ];
  var sort_row = table.find('thead tr.datatable_head').first() || null;

  if (sort_row) {
    order_by_default = sort_row.data('order_by_default') || null;
  }

  // {'formatted-num': [1,2,3], 'ip-address': [4,5,6]}
  if (typeof(custsort) !== 'undefined') {
    _.each(custsort, function(val, key) {
      column_defs.push({'sType': key, 'aTargets': val});
    });
  }

  var dt_options = {
    'bProcessing': false,
    'bPaginate': false,
    'bLengthChange': false,
    'bFilter': false,
    'bInfo': false,
    'bSort': true,
    'aoColumnDefs': column_defs,
  };

  if (order_by_default) {
    dt_options['aaSorting'] = order_by_default;
  }

  // Initialize dataTable
  if (!table.find('p.msg').length && table.find('tbody tr').length) {
    table.dataTable(dt_options);
  }
}


/*********
 * obj_list_sort_db
 */
function obj_list_sort_db(table) {
  var sort_row = table.find('thead tr.sortable').first();

  if (!sort_row.length) {
    return false;
  }

  table.addClass('dataTable');

  var order_by = sort_row.data('order_by') || '';
  var order_by_default = sort_row.data('order_by_default') || '';
  var sort_cols = sort_row.find('th');
  var url = window.location.pathname;
  var qs = parse_query_string();
  var sort_order, sort_msg, sort_cls, th, field, new_order;

  if (order_by.lastIndexOf('-', 0) === 0) {
    sort_order = 'desc';
    order_by = order_by.substring(1);
  } else {
    sort_order = 'asc';
  }

  sort_cols.each(function() {
    th = $(this);
    field = th.data('field');
    sort_msg = 'sort column ascending';
    sort_cls = 'sorting';

    if (field) {
      new_order = field;

      if (field == order_by) {
        sort_cls += '_' + sort_order;

        if (sort_order == 'asc') {
          sort_msg = 'sort column descending';
          new_order = '-' + field;
        }
      }

      if (order_by_default && (field != order_by_default)) {
        new_order += ',' + order_by_default;
      }

      qs['order_by'] = new_order;
      th.data('sort_link', window.location.pathname + '?' + $.param(qs));
      th.addClass(sort_cls);

      th.attr('title', th.text() + ': ' + gettext(sort_msg)).click(function() {
        ajax_move(this, $(this).data('sort_link'));
        return false;
      });
    }
  });

  return order_by;
}


/*********
 * ObjList
 */
function ObjList(init, nosort, custsort, links, handler) {
  var links_selector = 'a.obj_edit';
  self = this;
  this.modal = null;
  this.elements = {
    'table': $('#etable'),
  };

  if (typeof(links) === 'undefined') {
    links = '#obj_form_modal';
    links_selector += ', a.obj_add';
  }

  // Enable action links
  if (links) {
    this.elements.table.find(links_selector).click(function() {
      self.modal = new obj_form_modal($(this), links, init, handler);
      return false;
    });
  }

  if (nosort === null) {  // DB level sorting
    obj_list_sort_db(this.elements.table);
  } else {  // dataTable JS sorting
    obj_list_sort_js(this.elements.table, nosort, custsort);
  }

  table_obj_added(this.elements.table.find('tbody tr.info'));
} // ObjList
