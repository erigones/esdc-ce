var DC_DOMAINS = null;
function DcDomainList() {
  var self = this;

  // Sortable list
  this.list = new ObjList($.noop, [-1], {'icon-tag': [3]}, null);

  // Edit modal (attach/detach, delete, update)
  this.list.elements.table.find('a.obj_edit, a.obj_edit_or_add_dc').click(function() {

    self.list.modal = new obj_form_modal($(this), '#obj_form_modal', function(mod) {
      var btn_delete_dc = mod.mod.find('a.vm_modal_delete_dc');
      var btn_create_dc = mod.mod.find('a.vm_modal_create_dc');

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
    });

    return false;
  });

  // Attach modal
  this.list.elements.table.find('a.obj_add_dc').click(function() {
    self.list.modal = new obj_form_modal($(this), '#obj_add_dc_modal', _update_name_choices);

    return false;
  });

} // DcDomainList
