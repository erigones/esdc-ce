/*********** ServerAdd class *************/
VM_ADD = null;
function ServerAdd() {
  var self = this;
  var elements = {
    'mod_add':      $('#vm_settings_modal'),
    'mod_import':   $('#vm_import_file_modal'),
    'btn_add':      $('a.vm_add'),
    'btn_import':   $('a.vm_import'),
    'btn_download': $('a.download_sample'),
    'iframe_sample':$('#iframe_with_sample_file'),
  };

  function init_add() {
    // Hide import modal
    elements.mod_import.modal('hide');

    // Add single server - copy alias to empty hostname field
    var field_alias = $('#id_opt-alias');
    var field_hostname = $('#id_opt-hostname');
    field_alias.focusout(function() {
      if (!field_hostname.val()) {
        field_hostname.val(field_alias.val());
      }
    });

    // Show single server add modal
    vm_settings_modal(null, elements.btn_add, '#vm_settings_modal');

    return false;
  }

  function init_import() {
    elements.mod_add.modal('hide');
    new obj_form_modal($(this), '#vm_import_file_modal');

    return false;
  }

  function init_download() {
    elements.iframe_sample.attr('src', $(this).data('source'));

    return false;
  }

  this.init_import2 = function() {
    $('a.vm_import2').click(init_import);
  };

  elements.btn_add.click(init_add);

  elements.btn_import.click(init_import);

  elements.btn_download.click(init_download);

  init_add();
} // ServerAdd
