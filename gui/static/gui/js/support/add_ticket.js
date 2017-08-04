// Add links to Support controls
function support_control_links(elem) {
  var links;

  if (typeof(elem) === 'undefined') {
    links = $('a.support_control');
  } else {
    links = elem.find('a.support_control');
  }

  links.each(function() {
    var btn = $(this);
    btn.click(function() {
      support_control(btn);
      return false;
    });
  });

  // Submit on pressing enter
  $('#add-ticket-form').find(':input:enabled:visible:first').focus();
}

// Support control commands
function support_control(btn) {
  if (btn.hasClass('disabled')) {
    return false;
  }

  var action = btn.attr('id').split('_');
  btn.addClass('disabled');
  setTimeout(function() { btn.removeClass('disabled'); }, 2000);
  
  switch(action[1]) {
    case 'addticket':
      var form = $('#add_ticket_form');
      return ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, xhr) {
        if (xhr.status == 278) {
          ajax_move(null, xhr.getResponseHeader('Location'));
        } else {
          form.html(data);
          scroll_to_form_error(form);
        }
      }, form.parent().serialize(), null, btn);

    default:
      return false;
  }
}
