var DC_TEMPLATES = null;
function DcTemplateList() {
  this.list = new ObjList(function(mod, start) {
    if (mod.add) {
      _update_name_choices();
    }
  }, [-1], {'icon-tag': [3]});
} // DcTemplateList
