from __future__ import unicode_literals
import json

from django import forms
from django.utils import six
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe

from taggit.utils import split_strip
from taggit.forms import TagField as _TagField

from gui.utils import tags_to_string
from gui.widgets import ArrayWidget, ArrayAreaWidget, DictWidget


SIZE_FIELD_MB_ADDON = mark_safe(' MB <small class="hidden-phone">&nbsp;&nbsp;&nbsp;<b>' + _('Hint') + ':</b> ' +
                                _('Press "1g" for 1024 MB') + '</b></small>')
SIZE_FIELD_PERCENT_ADDON = mark_safe(' %')


def parse_items(itemstring, sort=False):
    """Like taggit.utils.parse_tags, but without sorting"""
    if not itemstring:
        return []

    itemstring = force_text(itemstring)

    words = []
    buf = []
    # Defer splitting of non-quoted sections until we know if there are
    # any unquoted commas.
    to_be_split = []
    i = iter(itemstring)
    try:
        while True:
            c = six.next(i)
            if c == '"':
                if buf:
                    to_be_split.append(''.join(buf))
                    buf = []
                # Find the matching quote
                c = six.next(i)
                while c != '"':
                    buf.append(c)
                    c = six.next(i)
                if buf:
                    word = ''.join(buf).strip()
                    if word:
                        words.append(word)
                    buf = []
            else:
                buf.append(c)
    except StopIteration:
        # If we were parsing an open quote which was never closed treat
        # the buffer as unquoted.
        if buf:
            to_be_split.append(''.join(buf))

    if to_be_split:
        delimiter = ','

        for chunk in to_be_split:
            words.extend(split_strip(chunk, delimiter))

    if sort:
        words = list(set(words))
        words.sort()

    return words


class ArrayField(forms.CharField):
    widget = ArrayWidget

    def __init__(self, *args, **kwargs):
        self.tags = kwargs.pop('tags', False)
        super(ArrayField, self).__init__(*args, **kwargs)

    def clean(self, value):
        value = super(ArrayField, self).clean(value)

        try:
            return parse_items(value, sort=self.tags)
        except ValueError:
            raise forms.ValidationError(_('Please provide a comma-separated list of items.'))


class ArrayAreaField(forms.CharField):
    widget = ArrayAreaWidget

    def clean(self, value):
        value = super(ArrayAreaField, self).clean(value)

        if not value:
            return []

        try:
            result = json.loads(value)

            if not isinstance(result, list):
                raise ValueError
        except ValueError:
            raise forms.ValidationError(_('Please provide a valid JSON array.'))

        return result


class DictField(forms.CharField):
    widget = DictWidget

    def clean(self, value):
        value = super(DictField, self).clean(value)

        if not value:
            return {}

        try:
            result = json.loads(value)

            if not isinstance(result, dict):
                raise ValueError
        except ValueError:
            raise forms.ValidationError(_('Please provide a valid JSON object.'))

        return result


class IntegerArrayField(ArrayField):
    def clean(self, value):
        try:
            return map(int, super(IntegerArrayField, self).clean(value))
        except ValueError:
            raise forms.ValidationError(_('Please provide a comma-separated list of integers.'))


class TagField(_TagField):
    def __init__(self, *args, **kwargs):
        self.tag_choices = kwargs.pop('tag_choices', ())
        super(TagField, self).__init__(*args, **kwargs)

    def clean(self, value):
        return tags_to_string(super(TagField, self).clean(value))

    @property
    def tag_choices(self):
        return self._tag_choices

    @tag_choices.setter
    def tag_choices(self, value):
        # noinspection PyAttributeOutsideInit
        self._tag_choices = self.widget.tag_choices = list(value)
