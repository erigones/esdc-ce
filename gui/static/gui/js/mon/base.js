/*
 * Monitoring templates and hostgroups select2 helpers
 */

var MONITORING_TEMPLATES = null;
var MONITORING_TEMPLATES_ELEMENTS = null;
var MONITORING_HOSTGROUPS = null;
var MONITORING_HOSTGROUPS_ELEMENTS = null;

function _tags_get_helper(element, global_name, api_call) {
  var elements_store = global_name + '_ELEMENTS';

  return function(query) {
    if (query) {
      if (window[global_name] === null) {
        if (!SOCKET.socket.connected) {
          return [];
        }

        if ($.isArray(window[elements_store])) {
          window[elements_store].push(element);
        }

        esio('get', api_call);
        window[global_name] = [];
      }

      return window[global_name];
    }
  };
}

function mon_templates_reset() {
  MONITORING_TEMPLATES_ELEMENTS = [];
}

function mon_templates_enable(elements, options) {
  MONITORING_TEMPLATES = null;
  options = options || {};

  elements.each(function() {
    var input = $(this);
    var data = input.data('tags-choices');
    var tags_data;

    if (typeof(data) === 'undefined') {
      tags_data = _tags_get_helper(input, 'MONITORING_TEMPLATES', input.data('tags-api-call') || 'mon_template_list');
    } else {
      tags_data = data;
    }

    input.select2($.extend({tags: tags_data, dropdownCssClass: input.attr('class'), tokenSeparators: [',']}, options));
  });
}

function mon_templates_update(result) {
	if ($.isArray(MONITORING_TEMPLATES) && MONITORING_TEMPLATES.length === 0 && $.isArray(result)) {
		// MONITORING_TEMPLATES.extend()
		MONITORING_TEMPLATES.push.apply(MONITORING_TEMPLATES, _.pluck(result, 'name'));

    if (MONITORING_TEMPLATES_ELEMENTS) {
      $.each(MONITORING_TEMPLATES_ELEMENTS, function() {
        $(this).select2('updateResults');
      });
    }
	}
}


function mon_hostgroups_reset() {
  MONITORING_HOSTGROUPS_ELEMENTS = [];
}

function mon_hostgroups_enable(elements, options) {
  MONITORING_HOSTGROUPS = null;
  options = options || {};

  elements.each(function() {
    var input = $(this);
    var data = input.data('tags-choices');
    var tags_data;

    if (typeof(data) === 'undefined') {
      tags_data = _tags_get_helper(input, 'MONITORING_HOSTGROUPS', input.data('tags-api-call') || 'mon_hostgroup_list');
    } else {
      tags_data = data;
    }

    input.select2($.extend({tags: tags_data, dropdownCssClass: input.attr('class'), tokenSeparators: [',']}, options));
  });
}

function mon_hostgroups_update(result) {
	if ($.isArray(MONITORING_HOSTGROUPS) && MONITORING_HOSTGROUPS.length === 0 && $.isArray(result)) {
		// MONITORING_HOSTGROUPS.extend()
		MONITORING_HOSTGROUPS.push.apply(MONITORING_HOSTGROUPS, _.pluck(result, 'name'));

    if (MONITORING_HOSTGROUPS_ELEMENTS) {
      $.each(MONITORING_HOSTGROUPS_ELEMENTS, function() {
        $(this).select2('updateResults');
      });
    }
	}
}
