from django.db.models.fields import UUIDField
from django.utils.translation import ugettext_lazy as _
from django.utils.six import text_type, string_types

from vms.forms import fields as form_fields

__all__ = ('CommaSeparatedUUIDField',)


class CommaSeparatedUUIDField(UUIDField):
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
        return map(super().to_python, value)

    def from_db_value(self, value, expression, connection, context):
        return self.to_python(value)

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
