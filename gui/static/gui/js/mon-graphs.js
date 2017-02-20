var HISTORY_ZABBIX_GRAPH_MAX_PERIOD = 14400000;
var HISTORY_GRAPH_OBJECTS = {};
var HISTORY_GRAPH_OPTIONS = {
  xaxis: {
    mode: 'time',
    timezone: 'browser',
  },
  grid: {
    hoverable: true,
    clickable: true,
  },
  series: {
    shadowSize: 0,
    lines: {
      lineWidth: 1,
      fill: true,
      fillColor: { colors: [ { opacity: 0.2 }, { opacity: 0.8 } ] },
      steps: false,
    },
  },
  selection: {
    mode: 'x',
  },
  crosshair: {
    mode: 'x',
  },
};


function _get_graph_id(obj_type, hostname, graph_name, graph_params) {
  var valid_graph_params = _.pick(graph_params, 'nic_id', 'disk_id');

  return obj_type + '__' + hostname + '__' + graph_name + '__' + $.param(valid_graph_params);
}

/*********** MonitoringGraph class *************/
function MonitoringGraph(obj_type, hostname, graph_name, graph_params, graph_id) {
  var self = this;
  var chart = $(jq(graph_id || _get_graph_id(obj_type, hostname, graph_name, graph_params)));
  var plot = null;
  var options = null;
  var history_chooser_timer = null;
  var since = null;
  var until = null;
  var autorefresh = true;
  var autorefresh_timer = null;
  var drawing = false;
  var yaxis = null;

  if (!chart.length) { return null; }

  var elements = {
    win:        chart,
    header:     chart.find('div.tab-header'),
    control:    chart.find('div.graph_history_control a:not(.useless)'),
    chartable:  chart.find('table.chartable'),
    winctrl:    chart.find('span.window-control'),
    period:     chart.find('span.period'),
    tip:                    $('#graph_tooltip'),
    tip_template_history:   _.template($('#template-graph-tooltip-history').html()),
    tip_template_trend:     _.template($('#template-graph-tooltip-trend').html()),
  };

  elements.grapholder = elements.chartable.find('div.graph');
  elements.legend = elements.chartable.find('div.legend');
  elements.tip_text = elements.tip.find('div.tooltip-inner');

  function _now() {
    var date = new Date();
    return Math.floor(date.getTime() / 1000);
  }

  function _get_graph_data(additional_graph_params) {
    return $.extend({}, graph_params, additional_graph_params);
  }

  /*
   * Format value by using the yaxis.tickFormatter()
   */
  function _yformat(value) {
    if (yaxis && $.isFunction(yaxis.tickFormatter)) {
      return yaxis.tickFormatter(value, yaxis);
    } else {
      return Math.round(value);
    }
  }

  /*
   * Parse mon_*_history result and return plot data
   */
  function _parse_history(result) {
    var i, data = {};

    // items
    for (i = 0; i < result.items.length; i++) {
      var item = result.items[i];
      var label = item.name;

      if (item.units) {
        label = label + ' (' + item.units + ')';
      }

      data[item.itemid] = {
        'label': label,
        'data': [],
      };
    }

    // history
    for (i = 0; i < result.history.length; i++) {
      var point = result.history[i];
      var dataitem, value;

      if ('value' in point) {
        value = point.value = parseFloat(point.value);
      } else if ('value_avg' in point) {
        // TODO: draw value_max and value_min
        value = point.value_avg = parseFloat(point.value_avg);
        point.value_max = parseFloat(point.value_max);
        point.value_min = parseFloat(point.value_min);
      } else {
        continue;
      }

      dataitem = [parseInt(point.clock) * 1000, value];
      dataitem.source = point; // Save point metadata

      data[point.itemid]['data'].push(dataitem);
    }

    // object -> array
    return $.map(data, function(v, i){ return v; });
  }

  /*
   * Append new data to existing plot data and remove old data
   */
  function _update_history(newdata) {
    var dataset = plot.getData();

    for (var i = 0; i < newdata.length; i++) {
      var olddata = dataset[i].data;

      for (var j = 0; j < newdata[i].data.length; j++) {
        olddata.push(newdata[i].data[j]);
        olddata.shift();
      }
    }

    return dataset;
  }

  /*
   * Shrink dataset according to new ranges
   */
  function _zoom_history(from, to) {
    var dataset = plot.getData();

    for (var i = 0; i < dataset.length; i++) {
      var olddata = dataset[i].data;
      var newstart = 0;
      var newend = olddata.length;

      for (var j = 0; j < olddata.length; j++) {
        if (!newstart && olddata[j][0] >= from) {
          newstart = j;
        }
        if (olddata[j][0] >= to) {
          newend = j;
          break;
        }
      }

      dataset[i].data = olddata.slice(newstart, newend);
    }

    return dataset;
  }

  /*
   * Update period text field (from - to)
   */
  function _update_period(plot, canvascontext) {
    var axes = plot.getAxes();
    var since = moment(axes.xaxis.min).strftime(LONG_DATETIME_FORMAT);
    var until = moment(axes.xaxis.max).strftime(LONG_DATETIME_FORMAT);

    elements.period.text(since + ' - ' + until);
  }

  /*
   * Stop the wheel and enable graph
   */
  function _graph_enable() {
    elements.header.removeClass('loading-gif-header');
    elements.winctrl.show();
    elements.chartable.removeClass('disabled');
  }
  function _graph_enable_problem() {
    _graph_enable();
    elements.chartable.addClass('problem');
  }

  /*
   * Stop the wheel and enable graph
   */
  function _graph_loading() {
    elements.header.addClass('loading-gif-header');
    elements.winctrl.hide();
    elements.chartable.removeClass('problem').addClass('disabled');
  }

  /*
   * Calculate average, maximum and minimum values for currently showed graph range
   */
  function _graph_stats(flot, offset) {
    yaxis = flot.getAxes().yaxis;  // Initialize yaxis used by _yformat() as soon as possible

    $(flot.getData()).each(function() {
      if (!this.label) {
        return;
      }

      var min = Number.MAX_VALUE;
      var max = Number.MIN_VALUE;
      var label;

      $(this.data).each(function() {
        var _min, _max, _avg = this[1];

        if ('value_avg' in this.source) {
          _min = this.source.value_min;
          _max = this.source.value_max;
        } else {
          _min = _max = _avg;
        }

        if (_min < min) {
          min = _min;
        }
        if (_max > max) {
          max = _max;
        }
      });

      label = this.label.split(' | ', 1)[0];
      this.label = label + ' | min: '+ _yformat(min) + ' | max: '+ _yformat(max);
    });
  }

  /*
   * Tooltip control
   */
  function _tooltip_show(item) {
    var text, style;
    var point_data = item.series.data[item.dataIndex];

    if (point_data === undefined) {  // I don't why, but it happens sometimes
      return _tooltip_hide();
    }

    var point = point_data.source;
    var t = moment(point_data[0]).strftime(LONG_DATETIME_FORMAT);

    if ('value_avg' in point) {
      text = elements.tip_template_trend({value_avg: _yformat(point.value_avg),
                                          value_max: _yformat(point.value_max),
                                          value_min: _yformat(point.value_min),
                                          time: t});
      style = {top: item.pageY-30, left: item.pageX-1};
    } else {
      text = elements.tip_template_history({value: _yformat(point.value), time: t});
      style = {top: item.pageY-15, left: item.pageX-1};
    }

    elements.tip_text.html(text).css({color: item.series.color});
    elements.tip.css(style).addClass('in');
  }
  function _tooltip_hide() {
    elements.tip_text.html('');
    elements.tip.removeClass('in');
  }

  /*
   * Create data for mon_get_history()
   */
  function _get_kwargs(period) {
    var now = _now();
    var kwargs = {'period': period};

    switch (period) {
      case '1h':  kwargs.since = now - 3600; break;
      case '4h':  kwargs.since = now - 3600 * 4; break;
      case '12h': kwargs.since = now - 3600 * 12; break;
      case '1d':  kwargs.since = now - 3600 * 24; break;
      case '1w':  kwargs.since = now - 3600 * 24 * 7; break;
      case '2w':  kwargs.since = now - 3600 * 24 * 14; break;
      case '1m':  kwargs.since = now - 3600 * 24 * 30; break;
      case '1y':  kwargs.since = now - 3600 * 24 * 365; break;
      default:    kwargs.since = now - 3600; break;
    }

    return kwargs;
  }

  /*
   * Create mon_vm|node_history task
   */
  function _update(kwargs, timeout) {
    if (typeof(timeout) === 'undefined') {
      timeout = 10;
    }

    _graph_loading();

    // Wait a bit before creating the task
    clearTimeout(history_chooser_timer);

    history_chooser_timer = setTimeout(function() {
      // Disable the buttons now
      elements.control.addClass('disabled');
      // Emit
      if (mon_get_history(obj_type, hostname, graph_name, _get_graph_data(kwargs)) === null) { // Emit never happened, socketio disconnected
        // Enable buttons and red graph
        _graph_enable_problem();
        elements.control.removeClass('disabled');
      }
    }, timeout);
  }

  /*
   * Plot new graph
   */
  function _draw(result) {
    var dataset;

    // Prepare options
    if (!options) {
      options = $.extend(true, {legend: {show: true, container: elements.legend}}, HISTORY_GRAPH_OPTIONS, result.options);
      options.hooks = { processOffset: [_graph_stats], draw: [_graph_enable, _update_period] };
    }

    // Parse and/or update data and plot!
    drawing = true;
    if (plot && autorefresh && result.autorefresh) {
      dataset = _update_history(_parse_history(result));
      plot.setData(dataset);
      plot.setupGrid();
      plot.draw();
    } else {
      dataset = _parse_history(result);
      plot = $.plot(elements.grapholder, dataset, options);
      yaxis = plot.getAxes().yaxis;  // Initialize yaxis used by _yformat()
    }
    drawing = false;

    since = result.since;
    until = result.until;

    // Auto-refresh
    if (autorefresh && result.update_interval) {
      autorefresh_timer = setTimeout(function() {
        var kwargs = {since: result.until + 1, autorefresh: true};
        // Emit
        mon_get_history(obj_type, hostname, graph_name, _get_graph_data(kwargs));
      }, result.update_interval * 1000);
    }
  }


  this.draw = function(result, error) {
    // Enable buttons
    elements.control.removeClass('disabled');

    if (result) {
      _draw(result);
    } else {
      _graph_enable_problem();
      if (error) {
        elements.grapholder.append('<p class="msg">' + gettext(error) + '</p>');
      }
    }
  };

  this.initial_update = function() {
    _update(_get_kwargs('1h'), 1000);
  };

  this.is_displayed = function() {
    return Boolean($(chart.selector).length);
  };

  /*
   * Initialize
   */

  // Add selection handler
  elements.grapholder.on('plotselected', function (e, ranges) {
    if (plot && !drawing) {
      var to = ranges.xaxis.to;
      var from = ranges.xaxis.from;
      var now = Date.now();
      var limit = 30000;

      if ((now - HISTORY_ZABBIX_GRAPH_MAX_PERIOD) > to) { // Trends only
        limit = 3600000;
      }

      if ((to - from) < limit ) { // Zooming too much is prohibited
        plot.clearSelection(true);
        return false;
      }

      if ((until - to / 1000) > 60) {
        autorefresh = false; clearTimeout(autorefresh_timer); // Turn off autorefressh if we selected older parts of an 1 hour graph
      }

      // Update data
      var dataset = _zoom_history(from, to);

      // Re-draw
      plot.setData(dataset);
      plot.setupGrid();
      plot.draw();
      plot.clearSelection(true);  // Remove selection rectangle without firing a "plotunselected" event
      elements.control.removeClass('active');
    }
  });

  // Add handler for plot/point hover (disabled)
  elements.grapholder.on('plothover', function (e, pos, item) {
    if (item) {
      _tooltip_show(item);
    } else {
      _tooltip_hide();
    }
  });

  // Graph history control
  elements.control.click(function() {
    var btn = $(this);

    if (btn.hasClass('disabled')) {
      return false;
    }

    btn.addClass('active').siblings().removeClass('active');
    autorefresh = false; clearTimeout(autorefresh_timer);

    var period = btn.data('period');

    if (period == '1h') {
      autorefresh = true;
    }

    _update(_get_kwargs(period));

    return false;
  });

  // Graph window control
  elements.winctrl.find('a').click(function() {
    var btn = $(this);

    if (btn.hasClass('disabled')) {
      return false;
    }

    switch (btn.data('resize')) {
      case 'horizontal':
        elements.win.toggleClass('span6 span12');
        break;
      case 'vertical':
        elements.win.find('div.graph').toggleClass('tall');
        break;
    }

    return false;
  });

} // MonitoringGraph


// Create and save graph instances (obj_type = {vm|node})
function mon_history_init(obj_type, hostname, graphs) {
  for (i = 0; i < graphs.length; i++) {
    var graph = graphs[i];
    var key = _get_graph_id(obj_type, hostname, graph.name, graph.params);

    HISTORY_GRAPH_OBJECTS[key] = new MonitoringGraph(obj_type, hostname, graph.name, graph.params, key);
    HISTORY_GRAPH_OBJECTS[key].initial_update();
  }
}

// Get monitoring history and draw new graph (obj_type = {vm|node})
function mon_history_update(obj_type, hostname, graph_name, graph_params, result, error) {
  var key = _get_graph_id(obj_type, hostname, graph_name, graph_params);
  var mon_graph = HISTORY_GRAPH_OBJECTS[key];

  if (mon_graph && mon_graph.is_displayed()) {
    mon_graph.draw(result, error);
  }
}
