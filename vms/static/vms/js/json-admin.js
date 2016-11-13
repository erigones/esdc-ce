django.jQuery(document).ready(function() {
  django.jQuery('textarea.jsoneditor').each(function(i) {
    var json_field = django.jQuery(this);
    var json_editor = django.jQuery('<div id="json_editor_'+i+'" style="width: 600px; height: 600px;"></div>');

    json_field.before(json_editor);
    json_field.css({'width': '486px', 'height': '60px', 'margin-left': '106px', 'margin-top': '20px'});

    var editor = new jsoneditor.JSONEditor(json_editor.get(0), {
      'error': function() {
        console.log(this);
      },
      'change': function() {
        json_field.val(JSON.stringify(editor.get()));
        return false;
      },
    }, JSON.parse(json_field.val()));

    // Some interference between django admin and jsoneditor causes a submit event on click
    json_editor.find('div.menu button').click(function() {
      return false;
    });

    json_field.focusout(function() {
      try {
        editor.set(JSON.parse(json_field.val()));
      } catch(err) {
        alert(err);
        json_field.val(JSON.stringify(editor.get()));
      }
      return false;
    });

  });
});
