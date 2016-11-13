/* Script is hijacking user clicks on links and loads the page via ajax on background. */

var CURRENT_URL = window.location.href;
var TITLE = 'Danube Cloud';
var TIMEOUT = 60000;

function update_content(url, go_back_on_error) {
  if ((AJAX !== null) && (AJAX.readyState !== 4)) {
    return false;
  }

  // Custom loading screens should use the show_loading_screen function.
  // In case the loading screen stays visible on content change,
  // this will clear the backdrop.
  hide_loading_screen();

  // Show loading screen for ajax movement
  var backdrop = get_loading_screen();

  // Load will also remove the darkness
  AJAX = $.ajax({
    url: url,
    type: 'GET',
    cache: false,
    timeout: TIMEOUT,
    beforeSend: function(xhr, ajaxOptions) {
      backdrop.appendTo(document.body);
      $('body').css('cursor', 'wait');
    },
    complete: function(xhr) {
      AJAX = null;
      backdrop.detach();
      $('body').css('cursor', 'auto');
    },

    statusCode: {
      // jQuery has a funny way of handling 302 redirects
      '278': function(e, textStatus, xhr) {
        var new_url = xhr.getResponseHeader('Location');
        console.log('Message', 'AJAX redirect detected. AJAX moving to:', new_url);
        // This will trigger a new ajax_move -> update_content
        window.History.replaceState(null, TITLE, new_url);
      },
      // Classic redirect (redirect out of the authenticated section)
      '279': function(e, textStatus, xhr) {
        var new_url = xhr.getResponseHeader('Location');
        console.log('Message', 'AJAX redirect detected. Classic move to:', new_url);
        window.location.replace(new_url);
      },
      // Got a new page
      '200': function(data) {
        // Add the content retrieved from ajax and put it in the #main-body
        $('#main-body').html(data);
        // Update CURRENT_URL after successfull change
        CURRENT_URL = window.location.href;
      },
    },

    error: function(xhr, textStatus, errorThrown) {
      console.log('Error', 'URL: '+ url +' has error '+ xhr.status +' ('+ errorThrown +')');
      var msg = _ajax_error_message(xhr, textStatus, errorThrown) + '<br /><br />URL: ' + url;
      notify('error', msg, 10);

      if (go_back_on_error) {
        // Go to previous page
        window.History.pushState(null, TITLE, CURRENT_URL);
      }
    },
  });

  console.log('Message', 'Page: '+ url +' has been loaded by AJAX.');
}

function ajax_move(e, url_alt) {
  var btn = $(e);
  var url, url_abs;

  if (btn.hasClass('disabled')) {
    return false;
  }

  // Find link to follow
  if (typeof(url_alt) === 'undefined') {
    url = btn.attr('href');
    url_abs = e.href;
  } else {
    url = url_alt;
    url_abs = url_alt;
  }

  function strip_hash(u) {
    var hash_pos = u.indexOf('#');
    if (hash_pos > 0) {
      return u.substr(0, hash_pos);
    }
    return u;
  }

  if (strip_hash(CURRENT_URL) == strip_hash(url_abs)) {
    // Clicking on a link that points to already loaded page - reload page, but don't change history
    return update_content(url, false);
  } else {
    // Change URL in history, this will trigger AJAX page change
    return window.History.pushState(null, TITLE, url);
  }
}

$(document).ready(function() {
  CURRENT_URL = window.location.href;

  window.History.Adapter.bind(window, 'statechange', function() {
    var state = window.History.getState();
    console.log('Message', 'History has been changed ('+ state.title +'): '+ state.url);
    $(window).off('resize orientationchange'); // Unbind here, each page may bind to the resize event
    update_content(state.url, true);
  });

  // Apply to all links unless they have no-ajax class
  $('#main-body').on('click', 'a:not(.no-ajax, .select2-search-choice-close)', function(event) {
    ajax_move(this);
    //stop deault browser action
    return false;
  });

});
