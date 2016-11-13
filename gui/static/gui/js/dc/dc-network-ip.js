var DC_NETWORK_IPS = null;
function DcNetworkIPList(admin) {
  var self = this;
  var ips_del;

  if (admin) {
    ips_del = $('#ips_del');

    this.check_list = new CheckList();
    this.check_list.selected_changed = function(count) {
      if (count) {
        ips_del.removeClass('disabled');
      } else {
        ips_del.addClass('disabled');
      }
    };

    ips_del.click(function() {
      self.modal = new obj_form_modal($(this), '#ips_del_modal', function(mod, start) {
        if (start) {
          var ips = _.keys(self.check_list.selected);
          var text_new = mod.text.html().replace('__ips__', ips.join(', '));
          mod.text.html(text_new);
          $('#id_ips').val(ips);
        }
      });
    });

    $('#network_edit').click(function() {
      self.modal = new obj_form_modal($(this), '#network_modal');
      return false;
    });
  }

  this.list = new ObjList(function(mod) {
    if (!mod.add) {
      $('#id_count').parent().parent().hide();
    }
  }, null);
} // DcNetworkIPList


var DC_SUBNET_IPS = null;
function DcSubnetIPList() {
  this.list = new ObjList($.noop, null, null, null);
} // DcSubnetIPList
