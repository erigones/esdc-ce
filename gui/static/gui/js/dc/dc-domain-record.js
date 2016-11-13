var DC_DOMAIN_RECORDS = null;
function DcDomainRecordList() {
  var self = this;
  var records_del = $('#records_del');

  this.check_list = new CheckList();
  this.check_list.selected_changed = function(count) {
    if (count) {
      records_del.removeClass('disabled');
    } else {
      records_del.addClass('disabled');
    }
  };

  records_del.click(function() {
    self.modal = new obj_form_modal($(this), '#records_del_modal', function(mod, start) {
      if (start) {
        var records = _.keys(self.check_list.selected);
        var records_desc = _.pluck(self.check_list.selected, 'desc');
        var text_new = mod.text.html().replace('__records__', records_desc.join(', '));
        mod.text.html(text_new);
        $('#id_records').val(records);
      }
    });
  });

  this.list = new ObjList(function(mod, start) {
    var type = $('#id_type');
    var prio = $('#id_prio').closest('div.input');

    function type_change() {
      var type_val = type.val();

      if (type_val == 'MX' || type_val == 'SRV') {
        prio.show();
      } else {
        prio.hide();
      }
    }

    type.off('change').change(type_change);
    type_change();
  }, null);
} // DcDomainRecordList
