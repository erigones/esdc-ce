var DC_SETTINGS = null;
function DcSettings(input_tooltip_disabled_msg) {
  var self = this;
  var table = $('#dc_settings_table');
  var form = $('#dc_settings_form');
  var btn_update = $('#dc_settings_update');
  var select = null;
  var mdata_input = null;
  var array_input = null;

  function init_table() {
    select = table.find('select.input-select2');
    select.select2({width: '100%'});
    mdata_input = table.find('textarea.input-mdata');
    mdata_enable(mdata_input);
    array_input = table.find('textarea.input-array');
    array_enable(array_input);
  }

  function click_update() {
    var btn = btn_update;

    if (!btn || btn.hasClass('disabled')) {
      return false;
    }

    btn.addClass('disabled');
    setTimeout(function() { btn.removeClass('disabled'); }, 800);
    mdata_prepare(mdata_input);
    array_prepare(array_input);
    table.find(':input').removeProp('disabled');

    ajax('POST', form.data('source'), ATIMEOUT, function(data, textStatus, xhr) {
      if (xhr.status == 278) {
        ajax_move(null, xhr.getResponseHeader('Location'));
      } else if (xhr.status == 204) {
        // do nothing
      } else {
        table.html(data);
        init_table();
        scroll_to_form_error(form);
      }
    }, form.serialize(), null, btn);

    return false;
  }

  this.init = function() {
    init_table();
    btn_update.click(click_update);
  };

  this.init();

  form.on('keypress', {btn_enter: btn_update}, enter_click).find(':input:enabled:visible:first').focus();

  // set tooltip text for the global settings
  table.find('input:disabled, textarea:disabled').tooltip({title:input_tooltip_disabled_msg, placement: 'left'});
  table.find('input:disabled').parents('.span9').tooltip({title: input_tooltip_disabled_msg, placement: 'left'})

} // DcSettings
