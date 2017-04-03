var NODE_IMAGE = null;

function NodeImage(hostname, zpool) {
  var self = this;
  var multi_modal = $('#node_image_multi_modal');
  var multi_delete = $('#node_image_multi_delete');

  this.list = new ObjList(
    function(mod, start) {
      var vms_err_msg = $('#image_vms_error');

      if (!mod.add) { // delete action
        if (mod.btn.data('vms')) { // image is used by VMs
          mod.mod.find('a.vm_modal_delete').addClass('disabled');
          vms_err_msg.show();
          return;
        }
      }
      vms_err_msg.hide();
    },

    [-1], {'formatted-num': [-2, -3, -6], 'icon-tag': [3]}, '#obj_form_modal',

    function(e) {
      // define custom obj_form_modal handler
      var mod = self.list.modal.mod;

      if (e.data.action == 'delete' && !$(this).hasClass('disabled')) {
        node_delete_image(hostname, zpool, $('#id_name').val());  // Run task!
        mod.modal('hide');
      }
    }
  );

  this.is_displayed = function(check_hostname, check_zpool) {
    return Boolean($(jq('node_images_' + check_hostname + '_' + check_zpool)).length);
  };

  this.reload = function() {
    update_content(CURRENT_URL, false);
  };

  this.update_menu_total = function(hostname, zpool, add) {
    var total_menu = $(jq('total_'+ hostname +'_'+ zpool));

    if (total_menu.length) {
      if (add) {
        total_menu.html(parseInt(total_menu.html()) + 1);
      } else {
        total_menu.html(total_menu.html() - 1);
      }
    }
  };

  this.remove_row = function(img_name) {
    var img_row = $(jq('ns_image_' + img_name));
    var total = $('#total');

    if (img_row.length) {
      self.list.elements.table.fnDeleteRow(img_row.get(0));
      img_row.remove();
      total.html(total.html() - 1);
      self.update_menu_total(hostname, zpool, false);
    }
  };

  this.update_status = function(img_name, state, status_display) {
    var img_status = $(jq('ns_image_' + img_name) + ' .ns_image_status');
    var img_link = $(jq('ns_image_' + img_name) + ' a.ns-image-delete-button');

    if (img_status.length) {
      img_status.html(status_display);

      if (state == 1) { // ready
        img_link.removeClass('disabled');
      } else { // deleting
        img_link.addClass('disabled');
      }
    }
  };

  multi_delete.click(function() {
    // Array of image form objects suitable for DELETE node_image() operation
    var images = $('#etable tbody a.obj_edit:not(".disabled")[data-vms="0"]').map(function() { return $(this).data('form'); }).get();
    var image_aliases = _.pluck(images, 'alias_version');
    var multi_modal_yes = multi_modal.find('a.vm_modal_yes');
    var multi_images = multi_modal.find('#id_imf_images');  // Always re-fetch this object before displaying modal (#117)

    if (image_aliases.length) {
      multi_images.html(image_aliases.join(', '));
      multi_modal_yes.removeClass('disabled');
    } else {
      multi_images.html('');
      multi_modal_yes.addClass('disabled');
    }

    return vm_modal(multi_modal, multi_delete, function(e) {
      if (image_aliases.length) {
        node_cleanup_images(hostname, zpool);  // Run task!
      }
    });
  });

} // NodeImage

function node_image_update(hostname, zpool, img_name, done, state, status_display) {
  if (NODE_IMAGE) {
    if (NODE_IMAGE.is_displayed(hostname, zpool)) {
      if (done) {
        if (state) {
          NODE_IMAGE.reload();
        } else {
          NODE_IMAGE.remove_row(img_name);
        }
      } else {
        NODE_IMAGE.update_status(img_name, state, status_display);
      }

      return true;

    } else if (done) {
      if (state) {
        NODE_IMAGE.update_menu_total(hostname, zpool, true);
      } else {
        NODE_IMAGE.update_menu_total(hostname, zpool, false);
      }
    }
  }

  return false;
}
