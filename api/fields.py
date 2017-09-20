"""
Copied+modified from rest_framework.fields, which is licensed under the BSD license:
*******************************************************************************
Copyright (c) 2011-2016, Tom Christie
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.
Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*******************************************************************************

Serializer fields perform validation on incoming data.

They are very similar to Django's form fields.
"""
from __future__ import unicode_literals

import copy
import datetime
import inspect
import re
import warnings
import collections
from decimal import Decimal, DecimalException

from django import forms
from django.core import validators
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models.fields import BLANK_CHOICE_DASH
from django.http import QueryDict
from django.forms import widgets
from django.utils import timezone, six
from django.utils.encoding import is_protected_type, force_text, force_unicode, smart_text
from django.utils.translation import ugettext_lazy as _
from django.utils.dateparse import parse_date, parse_datetime, parse_time
from taggit.utils import parse_tags, split_strip

from api import settings as api_settings
from api.settings import ISO_8601
from api.compat import is_non_str_iterable
from api.validators import cron_validator, ip_validator, mac_address_validator, cidr_validator, ip_or_nic_validator

__all__ = (
    'Field',
    'WritableField',
    'ModelField',
    'BooleanField',
    'CharField',
    'URLField',
    'SlugField',
    'ChoiceField',
    'EmailField',
    'RegexField',
    'DateField',
    'DateTimeField',
    'TimeField',
    'IntegerField',
    'FloatField',
    'DecimalField',
    'FileField',
    'ImageField',
    'SerializerMethodField',
    'DisplayChoiceField',
    'IntegerChoiceField',
    'IPAddressField',
    'MACAddressField',
    'TimeStampField',
    'DictField',
    'TagField',
    'BaseArrayField',
    'ArrayField',
    'DictArrayField',
    'IntegerArrayField',
    'IPAddressArrayField',
    'CronField',
    'CIDRField',
    'IPNICField',
    'BaseDictField',
    'RoutesField',
    'MetadataField',
    'URLDictField',
    'SafeCharField',
)


SAFE_CHARS = re.compile(r'^[^<>%$&;\'"]*$')
TRUE_VALUES = frozenset(['t', 'T', 'true', 'True', 'TRUE', '1', 1, True])
FALSE_VALUES = frozenset(['f', 'F', 'false', 'False', 'FALSE', '0', 0, 0.0, False])


def get_boolean_value(value):
    """BooleanField.to_native()"""
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return bool(value)


def is_simple_callable(obj):
    """
    True if the object is a callable that takes no arguments.
    """
    function_ = inspect.isfunction(obj)
    method = inspect.ismethod(obj)

    if not (function_ or method):
        return False

    args, _, _, defaults = inspect.getargspec(obj)
    len_args = len(args) if function_ else len(args) - 1
    len_defaults = len(defaults) if defaults else 0

    return len_args <= len_defaults


def get_component(obj, attr_name):
    """
    Given an object, and an attribute name,
    return that attribute on the object.
    """
    if isinstance(obj, collections.Mapping):
        val = obj.get(attr_name)
    else:
        val = getattr(obj, attr_name)

    if is_simple_callable(val):
        return val()

    return val


def readable_datetime_formats(formats):
    _format = ', '.join(formats).replace(ISO_8601, 'YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z]')

    return humanize_strptime(_format)


def readable_date_formats(formats):
    _format = ', '.join(formats).replace(ISO_8601, 'YYYY[-MM[-DD]]')

    return humanize_strptime(_format)


def readable_time_formats(formats):
    _format = ', '.join(formats).replace(ISO_8601, 'hh:mm[:ss[.uuuuuu]]')

    return humanize_strptime(_format)


def humanize_strptime(format_string):
    # Note that we're missing some of the locale specific mappings that
    # don't really make sense.
    mapping = {
        "%Y": "YYYY",
        "%y": "YY",
        "%m": "MM",
        "%b": "[Jan-Dec]",
        "%B": "[January-December]",
        "%d": "DD",
        "%H": "hh",
        "%I": "hh",  # Requires '%p' to differentiate from '%H'.
        "%M": "mm",
        "%S": "ss",
        "%f": "uuuuuu",
        "%a": "[Mon-Sun]",
        "%A": "[Monday-Sunday]",
        "%p": "[AM|PM]",
        "%z": "[+HHMM|-HHMM]"
    }
    for key, val in mapping.items():
        format_string = format_string.replace(key, val)

    return format_string


class Field(object):
    read_only = True
    creation_counter = 0
    empty = ''
    type_name = None
    partial = False
    use_files = False
    form_field_class = forms.CharField
    type_label = 'field'

    def __init__(self, source=None, label=None, help_text=None):
        self.parent = None

        self.creation_counter = Field.creation_counter
        Field.creation_counter += 1

        self.source = source

        if label is None:
            self.label = None
        else:
            self.label = smart_text(label)

        if help_text is None:
            self.help_text = None
        else:
            self.help_text = smart_text(help_text)

        self._errors = []
        self._value = None
        self._name = None

    @property
    def errors(self):
        return self._errors

    # noinspection PyUnusedLocal,PyAttributeOutsideInit
    def initialize(self, parent, field_name):
        """
        Called to set up a field prior to field_to_native or field_from_native.

        parent - The parent serializer.
        field_name - The name of the field being initialized.
        """
        self.parent = parent
        self.root = parent.root or parent
        self.context = self.root.context
        self.partial = self.root.partial

        if self.partial:
            self.required = False

    def field_from_native(self, data, files, field_name, into):
        """
        Given a dictionary and a field name, updates the dictionary `into`,
        with the field and it's deserialized value.
        """
        return

    def field_to_native(self, obj, field_name):
        """
        Given an object and a field name, returns the value that should be
        serialized for that field.
        """
        if obj is None:
            return self.empty

        if self.source == '*':
            return self.to_native(obj)

        source = self.source or field_name
        value = obj

        for component in source.split('.'):
            value = get_component(value, component)
            if value is None:
                break

        return self.to_native(value)

    def to_native(self, value):
        """
        Converts the field's value into it's simple representation.
        """
        if is_simple_callable(value):
            value = value()

        if is_protected_type(value):
            return value
        elif is_non_str_iterable(value) and not isinstance(value, (dict, six.string_types)):
            return [self.to_native(item) for item in value]
        elif isinstance(value, dict):
            # Make sure we preserve field ordering, if it exists
            ret = collections.OrderedDict()
            for key, val in value.items():
                ret[key] = self.to_native(val)
            return ret

        return force_text(value)

    def attributes(self):
        """
        Returns a dictionary of attributes to be used when serializing to xml.
        """
        if self.type_name:
            return {'type': self.type_name}

        return {}

    def metadata(self):
        metadata = collections.OrderedDict()
        metadata['type'] = self.type_label
        metadata['required'] = getattr(self, 'required', False)
        optional_attrs = ['read_only', 'label', 'help_text', 'min_length', 'max_length']

        for attr in optional_attrs:
            value = getattr(self, attr, None)

            if value is not None and value != '':
                metadata[attr] = force_text(value, strings_only=True)

        return metadata


class WritableField(Field):
    """
    Base for read/write fields.
    """
    write_only = False
    default_validators = ()
    default_error_messages = {
        'required': _('This field is required.'),
        'invalid': _('Invalid value.'),
    }
    default = None

    # noinspection PyShadowingNames
    def __init__(self, source=None, label=None, help_text=None, read_only=False, write_only=False, required=None,
                 validators=(), error_messages=None, default=None, allow_empty=None, **kwargs):
        super(WritableField, self).__init__(source=source, label=label, help_text=help_text)

        self.read_only = read_only
        self.write_only = write_only

        assert not (read_only and write_only), "Cannot set read_only=True and write_only=True"

        if required is None:
            self.required = not read_only
        else:
            assert not (read_only and required), "Cannot set required=True and read_only=True"
            self.required = required

        if allow_empty is None:
            self.allow_empty = not self.required
        else:
            self.allow_empty = allow_empty

        messages = {}
        for c in reversed(self.__class__.__mro__):
            messages.update(getattr(c, 'default_error_messages', {}))
        messages.update(error_messages or {})
        self.error_messages = messages

        self.validators = list(self.default_validators + validators)
        self.default = self.default if default is None else default

    def __deepcopy__(self, memo):
        result = copy.copy(self)
        memo[id(self)] = result
        result.validators = self.validators[:]
        return result

    def get_default_value(self):
        if is_simple_callable(self.default):
            return self.default()
        return self.default

    def validate(self, value):
        if not self.allow_empty and value in validators.EMPTY_VALUES:
            raise ValidationError(self.error_messages['required'])

    def run_validators(self, value):
        if value in validators.EMPTY_VALUES:
            return

        errors = []

        for v in self.validators:
            try:
                v(value)
            except ValidationError as e:
                if hasattr(e, 'code') and e.code in self.error_messages:
                    message = self.error_messages[e.code]
                    if e.params:
                        message = message % e.params
                    errors.append(message)
                else:
                    errors.extend(e.messages)
        if errors:
            raise ValidationError(errors)

    def field_to_native(self, obj, field_name):
        if self.write_only:
            return None
        return super(WritableField, self).field_to_native(obj, field_name)

    def field_from_native(self, data, files, field_name, into):
        """
        Given a dictionary and a field name, updates the dictionary `into`,
        with the field and it's deserialized value.
        """
        if self.read_only:
            return

        try:
            data = data or {}
            if self.use_files:
                files = files or {}
                try:
                    native = files[field_name]
                except KeyError:
                    native = data[field_name]
            else:
                native = data[field_name]
        except KeyError:
            if self.default is not None and not self.partial:
                # Note: partial updates shouldn't set defaults
                native = self.get_default_value()
            else:
                if self.required:
                    raise ValidationError(self.error_messages['required'])
                return

        value = self.from_native(native)
        if self.source == '*':
            if value:
                into.update(value)
        else:
            self.validate(value)
            self.run_validators(value)
            into[self.source or field_name] = value

    def from_native(self, value):
        """
        Reverts a simple representation back to the field's value.
        """
        return value


class ModelField(WritableField):
    """
    A generic field that can be used against an arbitrary model field.
    """
    def __init__(self, *args, **kwargs):
        try:
            self.model_field = kwargs.pop('model_field')
        except KeyError:
            raise ValueError("ModelField requires 'model_field' kwarg")

        self.min_length = kwargs.pop('min_length',
                                     getattr(self.model_field, 'min_length', None))
        self.max_length = kwargs.pop('max_length',
                                     getattr(self.model_field, 'max_length', None))
        self.min_value = kwargs.pop('min_value',
                                    getattr(self.model_field, 'min_value', None))
        self.max_value = kwargs.pop('max_value',
                                    getattr(self.model_field, 'max_value', None))

        super(ModelField, self).__init__(*args, **kwargs)

        if self.min_length is not None:
            self.validators.append(validators.MinLengthValidator(self.min_length))
        if self.max_length is not None:
            self.validators.append(validators.MaxLengthValidator(self.max_length))
        if self.min_value is not None:
            self.validators.append(validators.MinValueValidator(self.min_value))
        if self.max_value is not None:
            self.validators.append(validators.MaxValueValidator(self.max_value))

    def from_native(self, value):
        rel = getattr(self.model_field, "rel", None)
        if rel is None:
            return self.model_field.to_python(value)
        else:
            # noinspection PyProtectedMember
            return rel.to._meta.get_field(rel.field_name).to_python(value)

    def field_to_native(self, obj, field_name):
        # noinspection PyProtectedMember
        value = self.model_field._get_val_from_obj(obj)
        if is_protected_type(value):
            return value
        return self.model_field.value_to_string(obj)

    def attributes(self):
        return {
            "type": self.model_field.get_internal_type()
        }


class BooleanField(WritableField):
    type_name = 'BooleanField'
    type_label = 'boolean'
    form_field_class = forms.BooleanField
    widget = widgets.CheckboxInput
    default_error_messages = {
        'invalid': _("'%s' value must be either True or False."),
    }
    empty = False

    def field_from_native(self, data, files, field_name, into):
        # HTML checkboxes do not explicitly represent unchecked as `False`
        # we deal with that here...
        if isinstance(data, QueryDict) and self.default is None:
            self.default = False

        return super(BooleanField, self).field_from_native(
            data, files, field_name, into
        )

    def from_native(self, value):
        return get_boolean_value(value)


class CharField(WritableField):
    type_name = 'CharField'
    type_label = 'string'
    form_field_class = forms.CharField

    def __init__(self, max_length=None, min_length=None, allow_none=False, *args, **kwargs):
        self.max_length, self.min_length = max_length, min_length
        self.allow_none = allow_none
        super(CharField, self).__init__(*args, **kwargs)
        if min_length is not None:
            self.validators.append(validators.MinLengthValidator(min_length))
        if max_length is not None:
            self.validators.append(validators.MaxLengthValidator(max_length))

    def from_native(self, value):
        if isinstance(value, six.string_types):
            return value

        if value is None:
            if self.allow_none:
                # Return None explicitly because smart_text(None) == 'None'. See #1834 for details
                return None
            else:
                return ''

        return smart_text(value)


class URLField(CharField):
    type_name = 'URLField'
    type_label = 'url'

    def __init__(self, schemes=('http', 'https'), **kwargs):
        if 'validators' not in kwargs:
            kwargs['validators'] = (validators.URLValidator(schemes=schemes),)
        super(URLField, self).__init__(**kwargs)


class SlugField(CharField):
    type_name = 'SlugField'
    type_label = 'slug'
    form_field_class = forms.SlugField
    default_error_messages = {
        'invalid': _("Enter a valid 'slug' consisting of letters, numbers, underscores or hyphens."),
    }
    default_validators = (validators.validate_slug,)

    def __init__(self, *args, **kwargs):
        super(SlugField, self).__init__(*args, **kwargs)


class ChoiceField(WritableField):
    type_name = 'ChoiceField'
    type_label = 'choice'
    form_field_class = forms.ChoiceField
    widget = widgets.Select
    default_error_messages = {
        'invalid_choice': _('Select a valid choice. %(value)s is not one of the available choices.'),
    }

    def __init__(self, choices=(), blank_display_value=None, *args, **kwargs):
        self.empty = kwargs.pop('empty', '')
        super(ChoiceField, self).__init__(*args, **kwargs)
        self.choices = choices
        if not self.required:
            if blank_display_value is None:
                blank_choice = BLANK_CHOICE_DASH
            else:
                blank_choice = [('', blank_display_value)]
            self.choices = blank_choice + self.choices

    def _get_choices(self):
        return self._choices

    def _set_choices(self, value):
        # Setting choices also sets the choices on the widget.
        # choices can be any iterable, but we call list() on it because
        # it will be consumed more than once.
        self._choices = self.widget.choices = list(value)

    choices = property(_get_choices, _set_choices)

    def metadata(self):
        data = super(ChoiceField, self).metadata()
        data['choices'] = [{'value': v, 'display_name': n} for v, n in self.choices]
        return data

    def validate(self, value):
        """
        Validates that the input is in self.choices.
        """
        super(ChoiceField, self).validate(value)
        if value and not self.valid_value(value):
            raise ValidationError(self.error_messages['invalid_choice'] % {'value': value})

    def valid_value(self, value):
        """
        Check to see if the provided value is a valid choice.
        """
        for k, v in self.choices:
            if isinstance(v, (list, tuple)):
                # This is an optgroup, so look inside the group for options
                for k2, v2 in v:
                    if value == smart_text(k2) or value == k2:
                        return True
            else:
                if value == smart_text(k) or value == k:
                    return True
        return False

    def from_native(self, value):
        value = super(ChoiceField, self).from_native(value)
        if value == self.empty or value in validators.EMPTY_VALUES:
            return self.empty
        return value


class EmailField(CharField):
    type_name = 'EmailField'
    type_label = 'email'
    form_field_class = forms.EmailField
    default_error_messages = {
        'invalid': _('Enter a valid email address.'),
    }
    default_validators = (validators.validate_email,)

    def from_native(self, value):
        ret = super(EmailField, self).from_native(value)
        if ret is None:
            return None
        return ret.strip()


class RegexField(CharField):
    type_name = 'RegexField'
    type_label = 'regex'
    form_field_class = forms.RegexField

    def __init__(self, regex, max_length=None, min_length=None, *args, **kwargs):
        super(RegexField, self).__init__(max_length, min_length, *args, **kwargs)
        self.regex = regex

    def _get_regex(self):
        return self._regex

    def _set_regex(self, regex):
        if isinstance(regex, six.string_types):
            regex = re.compile(regex)
        self._regex = regex
        if hasattr(self, '_regex_validator') and self._regex_validator in self.validators:
            self.validators.remove(self._regex_validator)
        self._regex_validator = validators.RegexValidator(regex=regex)
        self.validators.append(self._regex_validator)

    regex = property(_get_regex, _set_regex)


class DateField(WritableField):
    type_name = 'DateField'
    type_label = 'date'
    widget = widgets.DateInput
    form_field_class = forms.DateField
    default_error_messages = {
        'invalid': _("Date has wrong format. Use one of these formats instead: %s"),
    }
    empty = None
    input_formats = api_settings.DATE_INPUT_FORMATS
    format = api_settings.DATE_FORMAT

    # noinspection PyShadowingBuiltins
    def __init__(self, input_formats=None, format=None, *args, **kwargs):
        self.input_formats = self.input_formats if input_formats is None else input_formats
        self.format = self.format if format is None else format
        super(DateField, self).__init__(*args, **kwargs)

    def from_native(self, value):
        if value in validators.EMPTY_VALUES:
            return None

        if isinstance(value, datetime.datetime):
            if timezone and settings.USE_TZ and timezone.is_aware(value):
                # Convert aware datetimes to the default time zone
                # before casting them to dates (#17742).
                default_timezone = timezone.get_default_timezone()
                value = timezone.make_naive(value, default_timezone)
            return value.date()
        if isinstance(value, datetime.date):
            return value

        for fmt in self.input_formats:
            if fmt.lower() == ISO_8601:
                try:
                    parsed = parse_date(value)
                except (ValueError, TypeError):
                    pass
                else:
                    if parsed is not None:
                        return parsed
            else:
                try:
                    parsed = datetime.datetime.strptime(value, fmt)
                except (ValueError, TypeError):
                    pass
                else:
                    return parsed.date()

        msg = self.error_messages['invalid'] % readable_date_formats(self.input_formats)

        raise ValidationError(msg)

    def to_native(self, value):
        if value is None or self.format is None:
            return value

        if isinstance(value, datetime.datetime):
            value = value.date()

        if self.format.lower() == ISO_8601:
            return value.isoformat()
        return value.strftime(self.format)


class DateTimeField(WritableField):
    type_name = 'DateTimeField'
    type_label = 'datetime'
    widget = widgets.DateTimeInput
    form_field_class = forms.DateTimeField
    default_error_messages = {
        'invalid': _("Datetime has wrong format. Use one of these formats instead: %s"),
    }
    empty = None
    input_formats = api_settings.DATETIME_INPUT_FORMATS
    format = api_settings.DATETIME_FORMAT

    # noinspection PyShadowingBuiltins
    def __init__(self, input_formats=None, format=None, *args, **kwargs):
        self.input_formats = self.input_formats if input_formats is None else input_formats
        self.format = self.format if format is None else format
        super(DateTimeField, self).__init__(*args, **kwargs)

    def from_native(self, value):
        if value in validators.EMPTY_VALUES:
            return None

        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, datetime.date):
            value = datetime.datetime(value.year, value.month, value.day)
            if settings.USE_TZ:
                # For backwards compatibility, interpret naive datetimes in
                # local time. This won't work during DST change, but we can't
                # do much about it, so we let the exceptions percolate up the
                # call stack.
                warnings.warn("DateTimeField received a naive datetime (%s)"
                              " while time zone support is active." % value,
                              RuntimeWarning)
                default_timezone = timezone.get_default_timezone()
                value = timezone.make_aware(value, default_timezone)
            return value

        for fmt in self.input_formats:
            if fmt.lower() == ISO_8601:
                try:
                    parsed = parse_datetime(value)
                except (ValueError, TypeError):
                    pass
                else:
                    if parsed is not None:
                        return parsed
            else:
                try:
                    parsed = datetime.datetime.strptime(value, fmt)
                except (ValueError, TypeError):
                    pass
                else:
                    return parsed

        msg = self.error_messages['invalid'] % readable_datetime_formats(self.input_formats)

        raise ValidationError(msg)

    def to_native(self, value):
        if value is None or self.format is None:
            return value

        if self.format.lower() == ISO_8601:
            ret = value.isoformat()
            if ret.endswith('+00:00'):
                ret = ret[:-6] + 'Z'
            return ret
        return value.strftime(self.format)


class TimeField(WritableField):
    type_name = 'TimeField'
    type_label = 'time'
    widget = widgets.TimeInput
    form_field_class = forms.TimeField
    default_error_messages = {
        'invalid': _("Time has wrong format. Use one of these formats instead: %s"),
    }
    empty = None
    input_formats = api_settings.TIME_INPUT_FORMATS
    format = api_settings.TIME_FORMAT

    # noinspection PyShadowingBuiltins
    def __init__(self, input_formats=None, format=None, *args, **kwargs):
        self.input_formats = input_formats if input_formats is not None else self.input_formats
        self.format = format if format is not None else self.format
        super(TimeField, self).__init__(*args, **kwargs)

    def from_native(self, value):
        if value in validators.EMPTY_VALUES:
            return None

        if isinstance(value, datetime.time):
            return value

        for fmt in self.input_formats:
            if fmt.lower() == ISO_8601:
                try:
                    parsed = parse_time(value)
                except (ValueError, TypeError):
                    pass
                else:
                    if parsed is not None:
                        return parsed
            else:
                try:
                    parsed = datetime.datetime.strptime(value, fmt)
                except (ValueError, TypeError):
                    pass
                else:
                    return parsed.time()

        msg = self.error_messages['invalid'] % readable_time_formats(self.input_formats)

        raise ValidationError(msg)

    def to_native(self, value):
        if value is None or self.format is None:
            return value

        if isinstance(value, datetime.datetime):
            value = value.time()

        if self.format.lower() == ISO_8601:
            return value.isoformat()
        return value.strftime(self.format)


class IntegerField(WritableField):
    type_name = 'IntegerField'
    type_label = 'integer'
    form_field_class = forms.IntegerField
    empty = 0
    default_error_messages = {
        'invalid': _('Enter a whole number.'),
        'max_value': _('Ensure this value is less than or equal to %(limit_value)s.'),
        'min_value': _('Ensure this value is greater than or equal to %(limit_value)s.'),
    }

    def __init__(self, max_value=None, min_value=None, *args, **kwargs):
        self.max_value, self.min_value = max_value, min_value
        super(IntegerField, self).__init__(*args, **kwargs)

        if max_value is not None:
            self.validators.append(validators.MaxValueValidator(max_value))
        if min_value is not None:
            self.validators.append(validators.MinValueValidator(min_value))

    def from_native(self, value):
        if value in validators.EMPTY_VALUES:
            return None

        try:
            value = int(str(value))
        except (ValueError, TypeError):
            raise ValidationError(self.error_messages['invalid'])
        return value


class FloatField(WritableField):
    type_name = 'FloatField'
    type_label = 'float'
    form_field_class = forms.FloatField
    empty = 0
    default_error_messages = {
        'invalid': _("'%s' value must be a float."),
    }

    def from_native(self, value):
        if value in validators.EMPTY_VALUES:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            msg = self.error_messages['invalid'] % value
            raise ValidationError(msg)


class DecimalField(WritableField):
    type_name = 'DecimalField'
    type_label = 'decimal'
    form_field_class = forms.DecimalField
    empty = Decimal('0')
    default_error_messages = {
        'invalid': _('Enter a number.'),
        'max_value': _('Ensure this value is less than or equal to %(limit_value)s.'),
        'min_value': _('Ensure this value is greater than or equal to %(limit_value)s.'),
        'max_digits': _('Ensure that there are no more than %s digits in total.'),
        'max_decimal_places': _('Ensure that there are no more than %s decimal places.'),
        'max_whole_digits': _('Ensure that there are no more than %s digits before the decimal point.')
    }

    def __init__(self, max_value=None, min_value=None, max_digits=None, decimal_places=None, *args, **kwargs):
        self.max_value, self.min_value = max_value, min_value
        self.max_digits, self.decimal_places = max_digits, decimal_places
        super(DecimalField, self).__init__(*args, **kwargs)

        if max_value is not None:
            self.validators.append(validators.MaxValueValidator(max_value))
        if min_value is not None:
            self.validators.append(validators.MinValueValidator(min_value))

    def from_native(self, value):
        """
        Validates that the input is a decimal number. Returns a Decimal
        instance. Returns None for empty values. Ensures that there are no more
        than max_digits in the number, and no more than decimal_places digits
        after the decimal point.
        """
        if value in validators.EMPTY_VALUES:
            return None
        value = smart_text(value).strip()
        try:
            value = Decimal(value)
        except DecimalException:
            raise ValidationError(self.error_messages['invalid'])
        return value

    def validate(self, value):
        super(DecimalField, self).validate(value)
        if value in validators.EMPTY_VALUES:
            return
        # Check for NaN, Inf and -Inf values. We can't compare directly for NaN,
        # since it is never equal to itself. However, NaN is the only value that
        # isn't equal to itself, so we can use this to identify NaN
        if value != value or value == Decimal("Inf") or value == Decimal("-Inf"):
            raise ValidationError(self.error_messages['invalid'])
        sign, digittuple, exponent = value.as_tuple()
        decimals = abs(exponent)
        # digittuple doesn't include any leading zeros.
        digits = len(digittuple)
        if decimals > digits:
            # We have leading zeros up to or past the decimal point.  Count
            # everything past the decimal point as a digit.  We do not count
            # 0 before the decimal point as a digit since that would mean
            # we would not allow max_digits = decimal_places.
            digits = decimals
        whole_digits = digits - decimals

        if self.max_digits is not None and digits > self.max_digits:
            raise ValidationError(self.error_messages['max_digits'] % self.max_digits)
        if self.decimal_places is not None and decimals > self.decimal_places:
            raise ValidationError(self.error_messages['max_decimal_places'] % self.decimal_places)
        if (self.max_digits is not None and self.decimal_places is not None and
                whole_digits > (self.max_digits - self.decimal_places)):
            raise ValidationError(self.error_messages['max_whole_digits'] % (self.max_digits - self.decimal_places))

        return value


class FileField(WritableField):
    use_files = True
    type_name = 'FileField'
    type_label = 'file upload'
    form_field_class = forms.FileField
    widget = widgets.FileInput

    default_error_messages = {
        'invalid': _("No file was submitted. Check the encoding type on the form."),
        'missing': _("No file was submitted."),
        'empty': _("The submitted file is empty."),
        'max_length': _('Ensure this filename has at most %(max)d characters (it has %(length)d).'),
        'contradiction': _('Please either submit a file or check the clear checkbox, not both.')
    }

    def __init__(self, *args, **kwargs):
        self.max_length = kwargs.pop('max_length', None)
        self.allow_empty_file = kwargs.pop('allow_empty_file', False)
        super(FileField, self).__init__(*args, **kwargs)

    def from_native(self, data):
        if data in validators.EMPTY_VALUES:
            return None

        # UploadedFile objects should have name and size attributes.
        try:
            file_name = data.name
            file_size = data.size
        except AttributeError:
            raise ValidationError(self.error_messages['invalid'])

        if self.max_length is not None and len(file_name) > self.max_length:
            error_values = {'max': self.max_length, 'length': len(file_name)}
            raise ValidationError(self.error_messages['max_length'] % error_values)
        if not file_name:
            raise ValidationError(self.error_messages['invalid'])
        if not self.allow_empty_file and not file_size:
            raise ValidationError(self.error_messages['empty'])

        return data

    def to_native(self, value):
        return value.name


class ImageField(FileField):
    use_files = True
    type_name = 'ImageField'
    type_label = 'image upload'
    form_field_class = forms.ImageField
    default_error_messages = {
        'invalid_image': _("Upload a valid image. The file you uploaded was "
                           "either not an image or a corrupted image."),
    }

    def from_native(self, data):
        """
        Checks that the file-upload field data contains a valid image (GIF, JPG,
        PNG, possibly others -- whatever the Python Imaging Library supports).
        """
        f = super(ImageField, self).from_native(data)
        if f is None:
            return None

        from api.compat import Image
        assert Image is not None, 'Either Pillow or PIL must be installed for ImageField support.'

        # We need to get a file object for PIL. We might have a path or we might
        # have to read the data into memory.
        if hasattr(data, 'temporary_file_path'):
            _file = data.temporary_file_path()
        else:
            if hasattr(data, 'read'):
                _file = six.BytesIO(data.read())
            else:
                _file = six.BytesIO(data['content'])

        try:
            # load() could spot a truncated JPEG, but it loads the entire
            # image in memory, which is a DoS vector. See #3848 and #18520.
            # verify() must be called immediately after the constructor.
            Image.open(_file).verify()
        except ImportError:
            # Under PyPy, it is possible to import PIL. However, the underlying
            # _imaging C module isn't available, so an ImportError will be
            # raised. Catch and re-raise.
            raise
        except Exception:  # Python Imaging Library doesn't recognize it as an image
            raise ValidationError(self.error_messages['invalid_image'])
        if hasattr(f, 'seek') and callable(f.seek):
            f.seek(0)
        return f


class SerializerMethodField(Field):
    """
    A field that gets its value by calling a method on the serializer it's attached to.
    """

    def __init__(self, method_name, *args, **kwargs):
        self.method_name = method_name
        super(SerializerMethodField, self).__init__(*args, **kwargs)

    def field_to_native(self, obj, field_name):
        value = getattr(self.parent, self.method_name)(obj)
        return self.to_native(value)


class DisplayChoiceField(ChoiceField):
    def __init__(self, *args, **kwargs):
        super(DisplayChoiceField, self).__init__(*args, **kwargs)
        self.choices_dict = dict(self.choices)

    def to_native(self, value):
        native_value = super(DisplayChoiceField, self).to_native(value)

        try:
            return force_unicode(self.choices_dict[native_value])
        except KeyError:
            return native_value


class IntegerChoiceField(ChoiceField):

    def validate(self, value):
        super(ChoiceField, self).validate(value)

        if value is None and self.allow_empty:
            pass
        elif not self.valid_value(value):
            raise ValidationError(self.error_messages['invalid_choice'] % {'value': value})

    def from_native(self, value):
        if self.allow_empty and value in ('', None):
            return None

        try:
            value = int(str(value))
        except (ValueError, TypeError):
            raise ValidationError(IntegerField.default_error_messages['invalid'])

        return super(IntegerChoiceField, self).from_native(value)


class IPAddressField(RegexField):
    type_name = 'IPAddressField'
    default_error_messages = {
        'invalid': _('Enter a valid IPv4 address.'),
    }

    def __init__(self, *args, **kwargs):
        self.strict = kwargs.pop('strict', False)
        if self.strict:
            self.default_validators = (ip_validator,)
        super(IPAddressField, self).__init__(validators.ipv4_re, *args, **kwargs)


class MACAddressField(RegexField):
    type_name = 'MACAddressField'
    default_error_messages = {
        'invalid': _('Enter a valid MAC address.'),
    }

    def __init__(self, *args, **kwargs):
        mac_re = re.compile(r'^[0-9A-F][2-9A-F0]:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}$',
                            flags=re.I)
        kwargs['validators'] = (mac_address_validator,)
        super(MACAddressField, self).__init__(mac_re, *args, **kwargs)


class TimeStampField(IntegerField):
    type_name = 'TimeStampField'
    default_error_messages = {
        'invalid': _('Enter a valid timestamp.'),
        'max_value': _('Ensure this value is less than or equal to %(limit_value)s.'),
        'min_value': _('Ensure this value is greater than or equal to %(limit_value)s.'),
    }

    def __init__(self, *args, **kwargs):
        if 'min_value' not in kwargs:
            kwargs['min_value'] = 1358528540
        if 'max_value' not in kwargs:
            kwargs['max_value'] = 2147483647
        super(TimeStampField, self).__init__(*args, **kwargs)

    @staticmethod
    def one_hour_ago():
        return int((timezone.now() - timezone.timedelta(hours=1)).strftime('%s'))

    @staticmethod
    def now():
        return int(timezone.now().strftime('%s'))


class DictField(WritableField):
    """
    Classic dictionary field
    """
    def from_native(self, value):
        try:
            return dict(value)
        except Exception:
            raise ValidationError(self.error_messages['invalid'])


class TagField(WritableField):
    """
    https://github.com/alex/django-taggit
    """
    def _strict_tags(self, value):
        tag_re = re.compile(r'^[A-Za-z0-9_-]+$')  # No dots!

        for tag in value:
            if not tag_re.search(tag):
                raise ValidationError(self.error_messages['invalid'])

        return value

    def from_native(self, data):
        if isinstance(data, list):
            return self._strict_tags(data)

        if isinstance(data, six.string_types):
            try:
                return self._strict_tags(parse_tags(data))
            except ValueError:
                pass

        raise ValidationError(self.error_messages['invalid'])

    def to_native(self, obj):
        if isinstance(obj, list):
            return obj

        return [t.name for t in obj.all()]


class BaseArrayField(CharField):
    """
    List - array.
    """
    _field = NotImplemented
    type_name = 'ArrayField'
    type_label = 'list'

    def __init__(self, *args, **kwargs):
        self.max_items = kwargs.pop('max_items', None)
        self.min_items = kwargs.pop('min_items', None)
        self.exact_items = kwargs.pop('exact_items', None)
        # We want to use custom validators on each used field, not on the array itself:
        self._field.validators.extend(kwargs.pop('validators', ()))
        super(BaseArrayField, self).__init__(*args, **kwargs)

    def to_native(self, value):
        if not value:
            value = []

        if isinstance(value, six.string_types):
            value = split_strip(value)

        if isinstance(value, (list, tuple)):
            return [self._field.to_native(i) for i in value]

        return value

    def from_native(self, value):
        if not value:
            return []

        if isinstance(value, six.string_types):
            value = split_strip(value)

        if isinstance(value, (list, tuple)):
            return [self._field.from_native(i) for i in value]

        raise ValidationError(self.error_messages['invalid'])

    def validate(self, value):
        count = len(value)

        if self.exact_items is not None:
            if count != self.exact_items:
                raise ValidationError(_('Ensure this value has exactly %(exact)d items (it has %(count)d).') %
                                      {'exact': self.exact_items, 'count': count})

        if self.min_items is not None:
            if count < self.min_items:
                raise ValidationError(_('Ensure this value has at least %(min)d items (it has %(count)d).') %
                                      {'min': self.min_items, 'count': count})

        if self.max_items is not None:
            if count > self.max_items:
                raise ValidationError(_('Ensure this value has at most %(max)d items (it has %(count)d).') %
                                      {'max': self.max_items, 'count': count})

        for i in value:
            self._field.validate(i)

    def run_validators(self, value):
        for i in value:
            self._field.run_validators(i)


class ArrayField(BaseArrayField):
    """
    ArrayField without validation.
    """
    _field = CharField()
    type_name = 'ArrayField'
    type_label = 'list'


class DictArrayField(BaseArrayField):
    """
    ArrayField with dictionaries as items.
    """
    _field = DictField()
    type_name = 'DictArrayField'
    type_label = 'objects'


class IntegerArrayField(BaseArrayField):
    """
    ArrayField with number validation.
    """
    _field = IntegerField()
    type_name = 'IntegerArrayField'
    type_label = 'integers'


class IPAddressArrayField(BaseArrayField):
    """
    ArrayField with IPv4 validation.
    """
    _field = IPAddressField()
    type_name = 'IPAddressArrayField'
    type_label = 'IP addresses'


class CronField(CharField):
    """
    Char field with crontab format validation.
    """
    type_name = 'CronField'
    type_label = 'CRON schedule'
    default_validators = (cron_validator,)

    def __init__(self, *args, **kwargs):
        defaults = {'max_length': 100, 'help_text': _('Minute Hour Day Month Weekday.')}
        defaults.update(kwargs)
        super(CronField, self).__init__(*args, **defaults)


class CIDRField(CharField):
    """
    IPv4/subnet in cidr notation.
    """
    type_name = 'CIDRField'
    type_label = 'cidr'
    default_validators = (cidr_validator,)

    def __init__(self, *args, **kwargs):
        defaults = {'max_length': 32}
        defaults.update(kwargs)
        super(CIDRField, self).__init__(*args, **defaults)


class IPNICField(CharField):
    """
    IPv4/subnet in cidr notation.
    """
    type_name = 'IPNICField'
    type_label = 'ipnic'
    default_validators = (ip_or_nic_validator,)

    def __init__(self, *args, **kwargs):
        defaults = {'max_length': 16}
        defaults.update(kwargs)
        super(IPNICField, self).__init__(*args, **defaults)


class BaseDictField(WritableField):
    """
    Dictionary - object.
    """
    _key_field = NotImplemented
    _val_field = NotImplemented

    def __init__(self, *args, **kwargs):
        self.max_items = kwargs.pop('max_items', None)
        super(BaseDictField, self).__init__(*args, **kwargs)

    def to_native(self, value):
        ret = {}

        if value:
            for key, val in dict(value).items():
                ret[self._key_field.to_native(key)] = self._val_field.to_native(val)

        return ret

    def from_native(self, value):
        if not value:
            return {}

        if isinstance(value, six.string_types):
            try:
                value = dict([i.split(':') for i in split_strip(value)])
            except ValueError:
                raise ValidationError(self.error_messages['invalid'])

        if isinstance(value, dict):
            ret = {}

            for key, val in dict(value).items():
                ret[self._key_field.from_native(key)] = self._val_field.from_native(val)

            return ret

        raise ValidationError(self.error_messages['invalid'])

    def validate(self, value):
        items = value.items()

        if self.max_items:
            count = len(items)
            if count > self.max_items:
                raise ValidationError(_('Ensure this value has at most %(max)d items (it has %(count)d).') %
                                      {'max': self.max_items, 'count': count})

        for k, v in items:
            self._key_field.validate(k)
            self._val_field.validate(v)

    def run_validators(self, value):
        for k, v in value.items():
            self._key_field.run_validators(k)
            self._val_field.run_validators(v)


class RoutesField(BaseDictField):
    """
    Route dictionary. Example:
     {
         "10.2.2.0/24": "10.2.1.1",
         "10.3.0.1": "nics[1]"
     }
    """
    _key_field = CIDRField()
    _val_field = IPNICField()


class MetadataField(BaseDictField):
    _key_field = RegexField(r'^[A-Za-z0-9\.\-_:]+$', max_length=128)
    _val_field = CharField(max_length=65536)


class URLDictField(BaseDictField):
    _key_field = RegexField(r'^[a-z0-9][a-z0-9\.\-_]*$', max_length=32)
    _val_field = URLField()


class SafeCharField(RegexField):
    type_name = 'CharField'

    def __init__(self, *args, **kwargs):
        super(SafeCharField, self).__init__(SAFE_CHARS, *args, **kwargs)
