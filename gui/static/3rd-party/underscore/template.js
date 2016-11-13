(function() {

  _.templateSettings = {
    interpolate: /\{\{(.+?)\}\}/g,
    escape: /\{\{-(.+?)-\}\}/g,
  };

}).call(this);
