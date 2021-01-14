import json
import phonenumbers

from django import forms
from django.forms import widgets
from django.utils import six
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from frozendict import frozendict
from taggit.forms import TagWidget as _TagWidget

from api.utils.encoders import JSONEncoder
from gui.models import UserProfile


__all__ = (
    'NumberInput',
    'EmailInput',
    'URLInput',
    'TelInput',
    'TelPrefixInput',
    'ByteSizeInput',
    'ArrayWidget',
    'ArrayAreaWidget',
    'DictWidget',
    'TagWidget',
)

HTML5_ATTRS = frozendict({'autocorrect': 'off', 'autocapitalize': 'off', 'spellcheck': 'false'})


def edit_string_for_items(array, escape_space=True, escape_comma=True, sort=False):
    """Like taggit.utils.edit_string_for_tags, but with list/tuple as input and without sorting"""
    items = []
    for i in array:
        if not isinstance(i, six.string_types):
            i = str(i)
        if escape_space and ' ' in i:
            items.append('"%s"' % i)
        if escape_comma and ',' in i:
            items.append('"%s"' % i)
        else:
            items.append(i)

    if sort:
        items.sort()

    return ','.join(items)


# noinspection PyAbstractClass
class _DefaultAttrsWidget(widgets.Widget):
    default_attrs = None
    default_class = None

    def __init__(self, attrs=None):
        if self.default_attrs:
            # dict() converts default_attrs from frozendict to regular dict
            defaults = dict(self.default_attrs)

            if attrs:
                defaults.update(attrs)
        else:
            defaults = attrs

        super(_DefaultAttrsWidget, self).__init__(attrs=defaults)

        if self.default_class:
            self.attrs['class'] = (self.default_class + ' ' + self.attrs.get('class', '')).rstrip()


class ArrayWidget(_DefaultAttrsWidget, widgets.TextInput):
    tag_choices = None

    def __init__(self, *args, **kwargs):
        self.tags = kwargs.pop('tags', False)
        self.escape_space = kwargs.pop('escape_space', True)
        self.escape_comma = kwargs.pop('escape_comma', True)
        super(ArrayWidget, self).__init__(*args, **kwargs)

    def build_attrs(self, *args, **kwargs):
        if self.tag_choices:
            tags = json.dumps(self.tag_choices, indent=None, cls=JSONEncoder)
            kwargs['data-tags-choices'] = mark_safe(conditional_escape(tags))

        return super(ArrayWidget, self).build_attrs(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        if value is not None and not isinstance(value, six.string_types):
            value = edit_string_for_items(value, escape_space=self.escape_space, escape_comma=self.escape_comma,
                                          sort=self.tags)
        return super(ArrayWidget, self).render(name, value, attrs=attrs, renderer=renderer)


class ArrayAreaWidget(_DefaultAttrsWidget, widgets.Textarea):
    default_attrs = frozendict({'rows': 3, 'cols': 40})
    default_class = 'input-array'

    def render(self, name, value, attrs=None, renderer=None):
        if value is not None and not isinstance(value, six.string_types):
            value = json.dumps(value, indent=4, ensure_ascii=False)
        return super(ArrayAreaWidget, self).render(name, value, attrs=attrs, renderer=renderer)


class DictWidget(_DefaultAttrsWidget, widgets.Textarea):
    default_attrs = frozendict({'rows': 4, 'cols': 40})
    default_class = 'input-mdata'

    def render(self, name, value, attrs=None, renderer=None):
        if value is not None and not isinstance(value, six.string_types):
            value = json.dumps(value, indent=4, ensure_ascii=False)
        return super(DictWidget, self).render(name, value, attrs=attrs, renderer=renderer)


class NumberInput(_DefaultAttrsWidget, widgets.Input):
    """
    HTML5 input type for numbers.
    """
    input_type = 'number'
    default_attrs = HTML5_ATTRS


class EmailInput(_DefaultAttrsWidget, widgets.Input):
    """
    HTML5 input type for email address.
    """
    input_type = 'email'
    default_attrs = HTML5_ATTRS


class URLInput(_DefaultAttrsWidget, widgets.URLInput):
    """
    HTML5 input type for URL address.
    """
    input_type = 'url'
    default_attrs = HTML5_ATTRS


class TelInput(_DefaultAttrsWidget, widgets.Input):
    """
    HTML5 input type for url address
    """
    input_type = 'tel'
    default_attrs = HTML5_ATTRS


class ByteSizeInput(_DefaultAttrsWidget, widgets.TextInput):
    """
    HTML5 input type for url address
    """
    default_attrs = frozendict({'pattern': '[0-9.]+[BKMGTPEbkmgtpe]?'})


# noinspection PyAbstractClass
class TelPrefixSelect(widgets.Select):
    """
    A drop-down menu with international phone prefixes.
    """
    # noinspection PyUnusedLocal
    def __init__(self, attrs=None, choices=()):
        super(TelPrefixSelect, self).__init__(attrs=attrs, choices=UserProfile.PHONE_PREFIXES)

    def build_attrs(self, extra_attrs=None, **kwargs):
        attrs = super(TelPrefixSelect, self).build_attrs(extra_attrs=extra_attrs, **kwargs)
        attrs['class'] = 'input-select2'
        attrs.pop('maxlength', None)
        return attrs


# noinspection PyAbstractClass
class TelPrefixInput(widgets.MultiWidget):
    """
    A Widget that splits phone number input into:
    - a country select box for phone prefix
    - an input for local phone number
    """
    erase_on_empty_input = False

    # noinspection PyUnusedLocal
    def __init__(self, attrs=None, initial=None):
        if attrs:
            self.erase_on_empty_input = attrs.pop('erase_on_empty_input', False)
        multi_widgets = [TelPrefixSelect(attrs=attrs), TelInput(attrs=attrs)]
        super(TelPrefixInput, self).__init__(multi_widgets, attrs=attrs)

    def decompress(self, value):
        if value:
            # noinspection PyBroadException
            try:
                num = phonenumbers.parse(value)
            except Exception:
                return value.split(' ', 1)
            else:
                return ['+' + str(num.country_code), str(num.national_number)]

        return [None, None]

    def value_from_datadict(self, data, files, name):
        values = super(TelPrefixInput, self).value_from_datadict(data, files, name)
        if self.erase_on_empty_input and not values[1]:
            return ''
        else:
            return '%s %s' % tuple(values)


def clean_international_phonenumber(value):
    """
    Validate phone number taken from TelPrefixInput and return in format suitable for our DB.
    """
    invalid_number_message = _(u'The phone number entered is not valid.')

    try:
        num = phonenumbers.parse(value)
        if not phonenumbers.is_valid_number(num):
            raise forms.ValidationError(invalid_number_message)
    except phonenumbers.NumberParseException:
        raise forms.ValidationError(invalid_number_message)

    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


# noinspection PyAbstractClass
class TagWidget(_TagWidget):
    tag_choices = None

    def build_attrs(self, *args, **kwargs):
        if self.tag_choices:
            tags = json.dumps(self.tag_choices, indent=None, cls=JSONEncoder)
            kwargs['data-tags-choices'] = mark_safe(conditional_escape(tags))

        return super(TagWidget, self).build_attrs(*args, **kwargs)
