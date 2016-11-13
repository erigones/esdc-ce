"""
Incompatible with Django 1.8.
Support for database lookups is missing.
"""

import uuid

from django.core.exceptions import ValidationError
from django.db.models import SubfieldBase
from django.db.models.fields import Field, TextField
from django.utils.translation import ugettext_lazy as _
from django.utils.six import text_type, string_types, with_metaclass

from vms.forms import fields as form_fields

__all__ = ('UUIDField', 'CommaSeparatedUUIDField')


class UUIDField(with_metaclass(SubfieldBase, Field)):
    """
    Django 1.8 UUID DB field (without support for native uuid column).
    """
    description = 'Universally unique identifier'
    empty_strings_allowed = False
    default_error_messages = {
        'invalid': _("'%(value)s' is not a valid UUID."),
    }

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 32
        super(UUIDField, self).__init__(*args, **kwargs)

    def get_prep_value(self, value):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            try:
                value = uuid.UUID(value)
            except AttributeError:
                raise TypeError(self.error_messages['invalid'] % {'value': value})
        return value.hex

    def to_python(self, value):
        if value and not isinstance(value, uuid.UUID):
            try:
                return uuid.UUID(value)
            except ValueError:
                raise ValidationError(self.error_messages['invalid'], code='invalid', params={'value': value})
        return value

    def value_to_string(self, obj):
        val = self._get_val_from_obj(obj)
        if not val:
            return ''
        return text_type(val)

    def formfield(self, **kwargs):
        defaults = {
            'form_class': form_fields.UUIDField,
        }
        defaults.update(kwargs)
        return super(UUIDField, self).formfield(**defaults)


class CommaSeparatedUUIDField(with_metaclass(SubfieldBase, TextField)):
    """
    Comma-separated UUID field.
    """
    _uuid_field = UUIDField()
    description = _('Comma-separated list of UUIDs')

    def get_prep_value(self, value):
        value = self.to_python(value)
        return ','.join(map(self._uuid_field.get_prep_value, value))

    def to_python(self, value):
        if not value:
            return []
        if isinstance(value, string_types):
            value = value.split(',')
        return map(self._uuid_field.to_python, value)

    def value_to_string(self, obj):
        val = self._get_val_from_obj(obj)
        if not val:
            return ''
        return ','.join(map(text_type, val))

    def formfield(self, **kwargs):
        defaults = {
            'form_class': form_fields.CommaSeparatedUUIDField,
        }
        defaults.update(kwargs)
        return super(CommaSeparatedUUIDField, self).formfield(**defaults)
