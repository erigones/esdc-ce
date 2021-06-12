/************ UI CONTROL ************/
// Update user form according to usertype
function profile_user_form_usertype() {
  var profile_user_form = $('#profile_user_form');
  var usertype = profile_user_form.find('#usertype input[name=usertype]:checked');
  var current_usertype;

  if (!usertype.length) {
    return;
  }

  current_usertype = usertype.val();

  profile_user_form.find('input[data-usertype]').each(function() {
    var input = $(this);
    var tr = input.closest('tr');

    if (input.data('usertype') == current_usertype) {
      tr.show();
      //tr.fadeIn();
    } else {
      tr.hide();
      //tr.fadeOut();
    }
  });
}


// Add links to Profile controls
function profile_control_links(elem) {
  var links;

  if (typeof(elem) === 'undefined') {
    links = $('a.profile_control');
  } else {
    links = elem.find('a.profile_control');
  }
  links.each(function() {
    var btn = $(this);
    btn.click(function() {
      profile_control(btn);
      return false;
    });
  });

  $('#profile_form').on('keypress', {btn_enter: $('#profile_update')}, enter_click).find(':input:enabled:visible:first').focus();
  $('#profile_user_form input[name=usertype]').change(profile_user_form_usertype);
  $('#id_phone_0, #id_phone2_0, #id_alerting_phone_0').select2();
  $('#id_language, #id_timezone, #id_country, #id_country2, #id_currency, #id_groups').select2({width: '100%'});
  profile_user_form_usertype();
  profile_billing_address();
}


function profile_billing_address() {
  if(!$('#id_different_billing').is(':checked')) {
    $('#billing_address_details').hide();
    //$('#billing_address_details').fadeOut();
  } else {
    $('#billing_address_details').show();
    //$('#billing_address_details').fadeIn();
  }
}

// Profile control commands
function profile_control(btn) {
  if (!btn.length || btn.hasClass('disabled')) {
    return false;
  }

  var action = btn.attr('id').split('_');
  var mod;
  btn.addClass('disabled');
  setTimeout(function() { btn.removeClass('disabled'); }, 2000);

  switch(action[1]) {
    case 'update':
    case 'update2':
    case 'update3':
    case 'update4':
      var page = $('#profile_page');
      var form = page.find('#profile_form');
      form.find(':input').removeProp('disabled');
      return ajax('POST', page.data('source'), ATIMEOUT, function(data, textStatus, jqXHR) {
        if (jqXHR.status == 278) {
          ajax_move(null, jqXHR.getResponseHeader('Location'));
        } else {
          page.html(data);
          profile_control_links(page);
          scroll_to_form_error(form);
        }
      }, form.serialize(), null, btn);

    case 'display-apikeys':
      var apikeys = $('#profile_apikey_list');
      return ajax('GET', apikeys.data('source'), ATIMEOUT, function(data, textStatus, jqXHR) {
          apikeys.html(data);
          init_copy_text_to_clipboard();
        });

    case 'password':
      mod = $('#profile_password_modal');
      return vm_modal(mod, btn, function() {
        var form = mod.find('form');
        return ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, jqXHR) {
          if (jqXHR.status == 278) {
            mod.modal('hide');
            ajax_move(null, jqXHR.getResponseHeader('Location'));
          } else {
            form.html(data);
          }
        }, form.serialize());
      });

    case 'addsshkey':
      mod = $('#profile_addsshkey_modal');
      return vm_modal(mod, btn, function() {
        var form = mod.find('form');
        return ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, jqXHR) {
          if (jqXHR.status == 278) {
            mod.modal('hide');
            ajax_move(null, jqXHR.getResponseHeader('Location'));
          } else {
            form.html(data);
          }
        }, form.serialize());
      });

    case 'deletesshkey':
      mod = $('#profile_deletesshkey_modal');
      return vm_modal(mod, btn, function() {
        var form = mod.find('form');
        var post = form.serializeArray();
        post.push({'name': 'name', 'value': btn.data('name')});
        return ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, jqXHR) {
          if (jqXHR.status == 278) {
            mod.modal('hide');
            ajax_move(null, jqXHR.getResponseHeader('Location'));
          }
        }, $.param(post));
      });

    case 'verifyemail':
    case 'verifyphone':
      mod = $('#profile_activation_modal');
      return vm_modal(mod, btn, function() {
        var form = mod.find('form');
        return ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, jqXHR) {
          if (jqXHR.status == 278) {
            mod.modal('hide');
            ajax_move(null, jqXHR.getResponseHeader('Location'));
          } else {
            form.html(data);
          }
        }, form.serialize());
      });


    default:
      return false;
  }
}
