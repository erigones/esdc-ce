jQuery.extend(jQuery.fn.dataTableExt.oSort, {
  'crontab-pre': function(a) {
    var crontab_entry = a.split(' ');
    var result = '';
    var item;

    // Use only minute and hour and ignore the rest
    for (i=1; i >= 0; i--) {
      item = crontab_entry[i].match(/(\d+)/);

      if (item) {
        result += (item[1] || '0').padStart(2, '0');
      } else {
        result += '00';
      }
    }

    return parseInt(result) || 0;
  },

	'crontab-asc': function(a, b) {
		return a - b;
	},

	'crontab-desc': function(a, b) {
		return b - a;
	}
});
