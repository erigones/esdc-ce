var DC_STORAGES = null;
function DcStorageList(node_zpool) {
  this.list = new ObjList(function(mod, start) {
    var node = $('#id_node');
    var zpool = $('#id_zpool');

    function node_change() {
      zpool.empty();
      _.each(node_zpool[node.val()], function(zpool_alias, i, all) {
        zpool.append($('<option></option>').attr('value', zpool_alias[0]).text(zpool_alias[1]));
      });
      zpool.select2('val', '');
    }

    if (mod.add) {
      node.find('option').each(function() {
        if (!_.has(node_zpool, $(this).val())) {
          $(this).remove();
        }
      });
      node.off('change').change(node_change);
      node_change();
    }
  }, [-1], {'formatted-num': [-2, -3, -4, -5, -6]});
} // DcStorageList
