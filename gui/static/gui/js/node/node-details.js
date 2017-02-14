var NODE = null;
function Node(hostname) {
  this.hostname = hostname;

  var refresh_btn = $('#node_sysinfo');
  function refresh() {
    if (refresh_btn.hasClass('disabled')) {
      return false;
    }

    refresh_btn.addClass('disabled');
    setTimeout(function() {
      refresh_btn.removeClass('disabled');
    }, 1500);

    node_sysinfo(hostname);

    return false;
  }

  $('#node_define').click(function() {
    new obj_form_modal($(this), '#node_define_modal');

    return false;
  });

  refresh_btn.click(refresh);

  SIGNALS.view_node_details.dispatch(this);
} // Node


// Refresh node details page if needed
function node_refresh_page(hostname) {
  if (!$(jq('node_header_' + hostname)).length) {
    return false;
  }
  update_content(CURRENT_URL, false);
  return true;
}

// Update node label according to status
function node_label_update(hostname, state, status_display) {
  var label = $(jq('node_label_' + hostname)); // escaping dots in hostname
  if (!label.length) {
    return;
  }

  label.data('status_display', status_display);
  label.fadeOut('fast', function() {
    $(this).removeClass().addClass('label status_node' + state).text(status_display).fadeIn();
  });

}

// Callback for node status change event
function node_status_update(hostname, state, status_display) {
  var msg_node_status = $('#msg_node_status, ' + jq('msg_node_status_' + hostname));

  if (!node_refresh_page(hostname)) {
    node_label_update(hostname, state, status_display);
  }

  if (status_display === 'online') {
    msg_node_status.hide();
  }
  else {
    msg_node_status.show();
  }
}
