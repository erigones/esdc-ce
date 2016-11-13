from django.forms import widgets
from django.utils.six import iteritems
from django.utils.html import format_html
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from json import dumps


# noinspection PyAbstractClass
class DataSelect(widgets.Select):
    """
    Select widget with option label as model virt object.
    """
    def __init__(self, *args, **kwargs):
        self.label_attr = kwargs.pop('label_attr', 'alias')
        super(DataSelect, self).__init__(*args, **kwargs)

    def render_option(self, selected_choices, option_value, obj):
        option_label = getattr(obj, self.label_attr, None)

        if option_label is None:
            return super(DataSelect, self).render_option(selected_choices, option_value, obj)

        option_value = force_text(option_value)

        if option_value in selected_choices:
            selected_html = mark_safe(" selected='selected'")
            if not self.allow_multiple_selected:
                # Only allow for a single selection.
                selected_choices.remove(option_value)
        else:
            selected_html = ''

        return format_html(u"<option value='{0}'{1} title='{2}' data-object='{3}'>{4}</option>",
                           option_value, selected_html, obj.desc,
                           mark_safe(dumps(obj.web_data, indent=None).replace("'", "\\'")),
                           force_text(option_label))


# noinspection PyAbstractClass
class MetaDataSelect(widgets.Select):
    """
    Select widget with option value as tuple (value, metadata).
    """
    def render_option(self, selected_choices, option_value, option_label):
        try:
            properties = ' '.join('%s="%s"' % kv for kv in iteritems(option_value[2]))
        except IndexError:
            properties = ''

        metadata = option_value[1]
        option_value = force_text(option_value[0])

        if option_value in selected_choices:
            selected_html = mark_safe(' selected="selected"')
            if not self.allow_multiple_selected:
                # Only allow for a single selection.
                selected_choices.remove(option_value)
        else:
            selected_html = ''

        return format_html(u"<option value='{0}'{1} data-meta='{2}' {3}>{4}</option>",
                           option_value,
                           selected_html,
                           mark_safe(dumps(metadata, indent=None).replace("'", "\\'")),
                           mark_safe(properties),
                           force_text(option_label))
