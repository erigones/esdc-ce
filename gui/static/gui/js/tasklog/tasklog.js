var TASKS = {'PENDING': 0, 'SUCCESS': 0, 'FAILURE': 0, 'REVOKED': 0, 'RUNNING': []};

function _update_tasks_icon(tasks) {
  if (TASKS['PENDING'] > 0) {
    tasks.addClass('loading-gif-navi');
  } else {
    tasks.removeClass('loading-gif-navi');
  }
}

function _flash_tasks_icon(tasks) {
  for (var i=0; i<2; i++) {
    tasks.fadeTo(300, 0.3).fadeTo(300, 1.0);
  }
}

function update_tasks_link() {
  var tasks = $('#tasks');

  if (!is_touch_device()) {
    tasks.hover(function() {
      $("#cached-tasks:parent").slideToggle();
    });
  }
  _update_tasks_icon(tasks);
  // Cached tasks width (cannot set properly with css)
  $('#cached-tasks').width($('#main').width());
}

function _update_tasklog_cached() {
  var cached_tasks = $('#cached-tasks');
  var url = TASKLOG_URL;
  var enabled = true;

  if (cached_tasks.data('disabled')) {
    url += '?disable_cached_tasklog=1';
    enabled = false;
  }

  console.log('Updating cached tasklog');

  return $.ajax({
    type: 'GET',
    url: url,
    dataType: 'html',
    timeout: 5000,
    success: function(data, textStatus, jqXHR) {
      // load data
      cached_tasks.html(data);
      console.log('TASKS', TASKS);

      // tasklog icon
      if (enabled) {
        var tasks = $('#tasks');
        _update_tasks_icon(tasks);
        _flash_tasks_icon(tasks);
      }

      // tasklog views
      if (cached_tasks.data('tasklog')) {
        var running = TASKS['RUNNING'];

        $.each($('#tasklog tr.PENDING'), function(i, e) {
          var entry = $(this);
          entry.removeClass('running');

          if (_.contains(running, entry.data('task_id'))) {
            entry.addClass('running');
          }
        });
      }
    }
  });
}

// Run _update_tasklog_cached() as soon as you call it for the first time, and,
// if you call it again any number of times during the wait period, as soon as that period is over.
update_tasklog_cached = _.throttle(_update_tasklog_cached, 500);

function tasklog_init(disable_cached) {
  var tasklog = $('#tasklog');
  var cached_tasklog = $('#cached-tasks');
  var show_detail_chars = 82;
  var show_detail_limit = 72;
  var detail_template = _.template($('#template-log-detail').html());

  if ($(window).width() < 640) {
    show_detail_chars = 0;
    show_detail_limit = 0;
  }

  obj_list_sort_db($('#tasklog-table'));

  $.each(tasklog.find('tr'), function(i, e) {
    var entry = $(this);
    var task_id = entry.data('task_id');
    var detail_td = entry.find('td.log-detail');
    var detail_pre = detail_td.find('pre');
    var detail_content;

    entry.hover(function() {
      $.each(tasklog.find("tr." + task_id), function(i, tr) {
        $(tr).addClass('info');
      });
    }, function() {
      $.each(tasklog.find("tr." + task_id), function(i, tr) {
        $(tr).removeClass('info');
      });
    });

    if (detail_pre.length) {
      detail_content = detail_pre.html();

      if (detail_content.length > show_detail_chars) {
        var show = detail_content.substr(0, show_detail_limit);
        var html = detail_template({'less': show, 'orig': detail_content});
        detail_td.html(html);
      }
    }
  });

  $('span.log-detail-less').on('click', function() {
    var span = $(this);
    var td = span.parent();
    var tr = td.parent();

    span.hide();
    td.find('span.log-detail-more').show();

    if (!show_detail_chars) {
      tr.find('td.log-user').hide();
      tr.find('td.log-msg').hide();
      td.attr('colspan', '3');
    }

    return false;
  });

  $('span.log-detail-more').on('click', function() {
    var span = $(this);
    var td = span.parent();
    var tr = td.parent();

    span.hide();
    td.find('span.log-detail-less').show();

    if (!show_detail_chars) {
      tr.find('td.log-user').show();
      tr.find('td.log-msg').show();
      td.removeAttr('colspan');
    }

    return false;
  });

  cached_tasklog.data('tasklog', true);

  if (disable_cached) {
    cached_tasklog.data('disabled', true);
  }
}
