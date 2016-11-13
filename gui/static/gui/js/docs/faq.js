function FAQView() {
  var list = $('#faq-content').find('> li');
  var toc = $('#faq-toc');
  var toc_item_template = _.template($('#template-toc-item').html());
  var toc_items = [];

  list.each(function(i) {
    var e = $(this);
    var id = i + 1;
    var subject = e.find('h4:first');
    var item = $(toc_item_template({id: id, subject: subject.text()}));

    toc.append(item);
    toc_items.push(item);
    subject.prepend('<span class="faq-id">' + id + '.</span>');
    e.attr('id', 'faq-question-' + id);
  });

  $('#faq-search').on('keyup', function() {
    var input = $(this).val();
    var search;

    if (input.length) {
      search = new RegExp(input, 'i');

      list.each(function(i) {
        var e = $(this);

        if (search.test(e.text())) {
          e.show();
          toc_items[i].show();
        } else {
          e.hide();
          toc_items[i].hide();
        }
      });
    } else {
      list.each(function(i) {
        var e = $(this);

        e.show();
        toc_items[i].show();
      });
    }
  });

  $('#faq-header').show();
}
