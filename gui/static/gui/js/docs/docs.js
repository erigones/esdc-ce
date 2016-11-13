function IframeView(iframe_id, header_id, loading_msg) {
  var win = $(window);
  var doc = $(iframe_id);
  var header = $(header_id);

  function get_doc_height() {
    return doc.contents().find("html").height();
  }

  function get_doc_width() {
    // Rescan header
    return $(header_id).outerWidth();
  }

  function resize_doc_iframe() {
    // Set iframe size twice on purpose
    doc.height(get_doc_height());
    doc.width(get_doc_width());
    doc.height(get_doc_height());
  }

  function scroll_doc_iframe() {
    // Scroll to anchor or top
    var iframe = doc.contents().get(0);
    var hash = iframe.location.hash;
    if (hash) {
      iframe.getElementById(hash.substring(1)).scrollIntoView();
    } else {
      header.get(0).scrollIntoView();
    }
  }

  function update_doc_iframe() {
    var contents;

    try {
      contents = doc.contents();
    } catch (e) {
      console.log(e); // TypeError: a.contentWindow is null
      return null;
    }

    if (contents.length) {
      resize_doc_iframe();
      scroll_doc_iframe();
      // Search problem
      if (contents.get(0).location.pathname.indexOf('search.html') >= 0) {
        setTimeout(resize_doc_iframe, 1000);
        setTimeout(resize_doc_iframe, 5000);
      }
    }
  }

  show_loading_screen(loading_msg, false, true);
  doc.on('load', update_doc_iframe);
  doc.on('load', hide_loading_screen);
  doc.on('load', function() {
    win.on('resize orientationchange', update_doc_iframe);
  });
}
