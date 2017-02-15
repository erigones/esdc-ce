var DC_IMAGES = null;
function DcImageList(task_id) {
  var self = this;

  if (task_id) { LAST_TASKS[task_id] = 'image_manage'; }

  // Sortable list
  this.list = new ObjList($.noop, [-1], {'formatted-num': [4], 'icon-tag': [3, 7, 8]}, null);

  // Edit modal (attach/detach, delete, update)
  this.list.elements.table.find('a.obj_edit, a.obj_edit_or_add_dc').click(function() {

    self.list.modal = new obj_form_modal($(this), '#obj_form_modal', function(mod) {
      var btn_delete_dc = mod.mod.find('a.vm_modal_delete_dc');
      var btn_create_dc = mod.mod.find('a.vm_modal_create_dc');

      $('#id_adm-manifest_url').parent().parent().parent().hide();
      $('#id_adm-file_url').parent().parent().parent().hide();
      btn_delete_dc.hide();
      btn_create_dc.hide();

      if (!mod.add) {
        if (mod.btn.hasClass('obj_edit_or_add_dc')) {
          btn_create_dc.show();
          mod.mod.find('span.title_edit_or_add_dc').show();
          mod.mod.find('span.title_edit').hide();
        } else {
          btn_delete_dc.show();
          mod.mod.find('span.title_edit_or_add_dc').hide();
        }
      }
    });

    return false;
  });

  // Add modal
  this.list.elements.table.find('a.obj_add_admin').click(function() {

    self.list.modal = new obj_form_modal($(this), '#obj_form_modal', function(mod) {
      mod.mod.find('a.vm_modal_delete_dc, a.vm_modal_create_dc, span.title_edit_or_add_dc').hide();
      $('#id_adm-manifest_url').parent().parent().parent().show();
      $('#id_adm-file_url').parent().parent().parent().show();

      var alias = $('#id_adm-alias');
      var name = $('#id_adm-name');

      name.off('focusout').focusout(function() {
        if (!alias.val()) {
          alias.val(name.val());
        }
      });
    });

    return false;
  });

  // Attach modal
  this.list.elements.table.find('a.obj_add_dc').click(function() {
    self.list.modal = new obj_form_modal($(this), '#obj_add_dc_modal', _update_name_choices);
    return false;
  });

  this.is_displayed = function() {
    return Boolean($('#image_list').length);
  };

  this.remove_row = function(img_name) {
    var img_row = $(jq('image_' + img_name));
    var total;

    if (img_row.length) {
      self.list.elements.table.fnDeleteRow(img_row.get(0));
      img_row.remove();
      total = $('#total');
      total.html(total.html() - 1);
    }
  };

  this.update_status = function(img_name, state, status_display) {
    var img_status = $(jq('image_' + img_name) + ' .image_status');
    if (!img_status.length) {
      return;
    }
    var img_link = $(jq('image_' + img_name) + ' .edit-button');

    img_status.html(status_display);

    if (state == 2) {
      img_link.addClass('disabled');
    } else {
      img_link.removeClass('disabled');
    }
  };
} // DcImageList

function image_list_update(img_name, remove, state, status_display) {
  if (DC_IMAGES && DC_IMAGES.is_displayed()) {
    if (remove) {
      DC_IMAGES.remove_row(img_name);
    } else {
      DC_IMAGES.update_status(img_name, state, status_display);
    }
    return true;
  }
  return false;
}
