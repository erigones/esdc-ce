$.datepicker.setDefaults( $.datepicker.regional[ LANGUAGE_CODE ] );

function report_table_init() {
  var table = $('#cloud_customers_report_table');

  if (!table.find('p.msg').length && table.find('thead tr').length) { // error message
    table.dataTable({
      'bProcessing': false,
      'bPaginate': false,
      'bLengthChange': false,
      'bFilter': false,
      'bInfo': false,
      'bSort': true,
      'aoColumnDefs': [
        {'bSortable': false, 'aTargets': [0, -1, -2, -3]},
        {'bSearchable': false, 'aTargets': [0, -1, -2, -3]},
        {'sType': 'formatted-num', 'aTargets': [3, 4, 5, 6, 7, 8, 9]},
      ],
    });
  }
}

function filter_links() {
  var form = $('#filter_form');
  var dateinput = form.find('.input-date');

  form.find('a.filter_action').click(function() {
    filter_action(form, $(this));
    return false;
  });

  dateinput.datepicker({dateFormat: 'yy-mm-dd'});
}

function filter_action(form, btn) {
  if (btn.hasClass('disabled')) {
    return false;
  }

  var qs;
  var action = btn.attr('id').split('_');
  btn.addClass('disabled');
  setTimeout(function() { btn.removeClass('disabled'); }, 1000);

  switch(action[1]) {
    case 'clear':
      qs = form.find(':input.always-include-navigation').serialize();
      break;
    case 'filter':
      qs = form.serialize();
      break;
    default:
      return false;
  }

  return ajax_move(null, window.location.pathname + '?' + qs);
}
