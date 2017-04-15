var DC_NODES = null;
function DcNodeList() {
  this.list = new ObjList(function(mod, start) {
    var strategy = $('#id_strategy');
    var fields = $('#id_cpu, #id_ram, #id_disk');

    function strategy_change() {
      if (strategy.val() == 1) {
        fields.prop('disabled', true).addClass('uneditable-input').removeClass('input-transparent');
      } else {
        fields.removeProp('disabled').removeClass('uneditable-input').addClass('input-transparent');
      }
    }

    strategy.off('change').change(strategy_change);
    strategy_change();

    if (mod.add) {
      $('#etable tbody tr').each(function() {
        var hostname = $(this).data('hostname');
        if (hostname) {
          $('#id_hostname option[value="'+hostname+'"]').remove();
        }
      });
      strategy.select2('val', '');
    } else {
      $('#id_add_storage').parent().parent().hide();
    }

  }, [], {'formatted-num': [3, 4, 5, 6, 7, 8, 9, 10]});
} // DcNodeList
