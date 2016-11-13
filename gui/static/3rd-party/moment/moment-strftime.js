(function() {
  var moment, replacements;

  if (typeof require !== "undefined" && require !== null) {
    moment = require('moment');
  } else {
    moment = this.moment;
  }

  replacements = {
    a: 'ddd',
    A: 'dddd',
    b: 'MMM',
    B: 'MMMM',
    d: 'DD',
    F: 'YYYY-MM-DD',
    H: 'HH',
    I: 'hh',
    j: 'DDDD',
    m: 'MM',
    M: 'mm',
    p: 'A',
    S: 'ss',
    Z: 'z',
    w: 'd',
    y: 'YY',
    Y: 'YYYY',
    '%': '%'
  };

  moment.fn.strftime = function(format) {
    var key, momentFormat, value;
    momentFormat = format;
    for (key in replacements) {
      value = replacements[key];
      momentFormat = momentFormat.replace("%" + key, value);
    }
    return this.format(momentFormat);
  };

  if (typeof module !== "undefined" && module !== null) {
    module.exports = moment;
  } else {
    this.moment = moment;
  }

}).call(this);
