var NODE_STORAGE = null;

function NodeStorage(zpools) {
  this.list = new ObjList(function(mod, start) {
    var zpool = $('#id_zpool');
    var alias = $('#id_alias');

    function zpool_change() {
      if (!alias.val()) {
        alias.val(zpool.val());
      }
    }

    if (mod.add) {
      zpool.find('option').each(function() {
        if (!_.contains(zpools, $(this).val())) {
          $(this).remove();
        }
      });

      zpool.off('change').change(zpool_change);
      zpool_change();
    }

  }, [-1], {'formatted-num': [-2, -3, -4, -5, -6, -7, -8]});
} // NodeStorage
