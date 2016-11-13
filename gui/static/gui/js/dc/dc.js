// Emit user update if DC changes
function dc_check(current_dc) {
  if (current_dc != CURRENT_DC) {
    console.log('DC changed!');
    if (SOCKET.socket.connected) {
      SOCKET.emit('dc_switch');
      CURRENT_DC = current_dc;
    }
  }
}

function dc_switch_link() {
  $('#dc-switch').click(function() {
    vm_modal($('#dc_switch_modal'), $(this), function(e) {
      vm_modal_form_handler(e);
    });
    return false;
  });
}

// Used by other Dc*List classes
function _update_name_choices() {
  var name_field = $('#id_name');

  $('#etable tbody a.obj_edit').each(function() {
    var n = $(this).data('form');
    if (n && n.name) {
      name_field.find('option[value="'+ n.name +'"]').remove();
    }
  });

  name_field.select2('val', '');
}

var DCS = null;
function DcList() {
  this.list = new ObjList(function(mod, start) {
    if (mod.add) {
      mod.btn_more.hide();
      var alias = $('#id_alias');
      var name = $('#id_name');

      name.off('focusout').focusout(function() {
        if (!alias.val()) {
          alias.val(name.val());
        }
      });
    } else {
      mod.btn_more.show().one('click', function() {
        mod.mod.modal('hide');
        obj_form_modal(mod.btn.parent().parent().find('a.obj_more'), '#dc_settings_modal');
      });
    }
  }, [-1, -2], {'formatted-num': [-3, -4]});

  this.list.elements.table.find('a.obj_more').click(function() {
    obj_form_modal($(this), '#dc_settings_modal');
    return false;
  });
} // DcList
