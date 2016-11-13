var IMAGESTORE = null;
function ImageStoreList() {
  var self = this;
  // Sortable list
  this.list = new ObjList($.noop, [-1], {'formatted-num': [2]}, null);
  var table_rows = this.list.elements.table.find('tbody tr');

  // Import modal
  table_rows.find('a.imagestore-image').click(function() {
    self.list.modal = new obj_form_modal($(this), '#obj_form_modal', function(mod) {
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

  // Refresh button
  $('#imagestore-refresh').click(function() {
    var btn = $(this);
    var form = $('#imagestore-refresh-form');
    var errmsg = $('#imagestore-refresh-error');
    var err;

    if (!btn || btn.hasClass('disabled')) {
      return false;
    }
    btn.addClass('disabled');
    setTimeout(function() { btn.removeClass('disabled'); }, 1000);
    errmsg.hide();

    ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, xhr) {
      if (xhr.status == 278) {
        ajax_move(null, xhr.getResponseHeader('Location'));
      } else if (xhr.status == 204) {
        // do nothing
      } else {
        update_tasklog_cached();
        err = JSON.parse(data).result.error;
        errmsg.find('span').text(JSON.parse(data).result.error);
        errmsg.show();
        notify('error', err);
      }
    }, form.serialize(), null, btn);

    return false;
  });

  // Image search
  $('#image_search').keyup(function(e) {
    var val = $(this).val();

    if (val.length > 0) {
      var pattern = new RegExp(val, 'i');

      table_rows.each(function(i, e) {
        var tr = $(e);
        var image_name = tr.find('a.imagestore-image').text();

        if (pattern.test(image_name)) {
          tr.show();
        } else {
          tr.hide();
        }
      });

    } else {
      table_rows.each(function(i, e) {
        var tr = $(e);
        tr.show();
      });
    }
  }); // Node search

} // ImageStoreList
