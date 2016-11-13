import uuid

from django.forms.fields import CharField
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.utils.six import text_type, string_types

__all__ = ('UUIDField', 'CommaSeparatedUUIDField')


class UUIDField(CharField):
    """
    Django 1.8. UUID form field.
    """
    default_error_messages = {
        'invalid': _('Enter a valid UUID.'),
    }

    def prepare_value(self, value):
        if isinstance(value, uuid.UUID):
            return value.hex
        return value

    def to_python(self, value):
        value = super(UUIDField, self).to_python(value)
        if value in self.empty_values:
            return None
        if not isinstance(value, uuid.UUID):
            try:
                value = uuid.UUID(value)
            except ValueError:
                raise ValidationError(self.error_messages['invalid'], code='invalid')
        return value


class CommaSeparatedUUIDField(CharField):
    """
    Comma-separated UUID field.
    """
    default_error_messages = {
        'invalid': _('Enter only valid UUIDs separated by commas.'),
    }

    def prepare_value(self, value):
        if isinstance(value, (list, tuple)):
            return ','.join(map(text_type, value))
        return value

    def to_python(self, value):
        value = super(CommaSeparatedUUIDField, self).to_python(value)
        if value in self.empty_values:
            return []
        if isinstance(value, string_types):
            value = value.split(',')
        try:
            return map(uuid.UUID, value)
        except ValueError:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
