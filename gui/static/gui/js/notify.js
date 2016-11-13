/*
 * Expected to exist
 */
Array.prototype.remove = function(value) {
  var i = _.indexOf(this, value);

  if (i !== -1) {
    return this.splice(i, 1);
  }
};


/*
 * NotificationElement
 */
function NotificationElement(parent, template, options) {
  var self = this;
  this.element = $(template(options));

  this.dismiss = function() {
    return self.element.slideUp().queue(function() {
      parent.remove(self);
      self.element.remove();
    });
  };

  this.element.find('i.hide').on('click touchend', self.dismiss);

  if (options.auto_dismiss) {
    setTimeout(self.dismiss, options.auto_dismiss * 1000);
  }
} // NotificationElement


/*
 * NotificationBar
 */
function NotificationBar() {
  var self = this;
  var items = [];
  var item_template = _.template($('#template-notification-element').html());
  var item_defaults = {main_class: '', image_class: '', icon_class: '', text: '', time: ''};
  var bar = $(_.template($('#template-notification-bar').html())({}));
  var bar_wrapper = bar.find('#notification-bar');
  var bar_elements = bar.find('#notification-elements');

  this._add = function(item) {
    bar_elements.prepend(item.element);

    if (items.length === 0) {
      bar_wrapper.addClass('flipInX');
    }

    items.push(item);
  };

  this.push = function(options) {
    var item = new NotificationElement(self, item_template, _.defaults(options, item_defaults));

    self._add(item);

    return item;
  };

  this.remove = function(item) {
    items.remove(item);

    if (items.length === 0) {
      bar_wrapper.removeClass('flipInX active');
    }
  };

  this.dismiss_all = function() {
    for (var i=0; i < items.length; i++) {
      items[i].dismiss();
    }
  };

  /* Initialize */
  $('body').prepend(bar);
  bar_wrapper.find('#dismiss-all').on('click', self.dismiss_all);
  bar_wrapper.on('touchstart', function() {
    $(this).addClass('active');
  });
} // NotificationBar
