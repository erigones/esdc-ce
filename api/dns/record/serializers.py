from api import serializers as s
from pdns.models import Record
from pdns.validators import RecordValidationError, run_record_validator


class RecordSerializer(s.InstanceSerializer):
    """
    pdns.models.Record
    """
    _model_ = Record
    _update_fields_ = ('name', 'type', 'content', 'ttl', 'prio', 'disabled')
    _null_fields_ = frozenset({'content', 'ttl', 'prio'})

    id = s.Field()
    domain = s.Field()
    name = s.CharField(max_length=253)  # Validated via pdns.validators
    type = s.ChoiceField(choices=Record.TYPE)
    content = s.CharField(max_length=65535, required=False)
    ttl = s.IntegerField(default=Record.TTL, required=False, min_value=0, max_value=2147483647)
    prio = s.IntegerField(default=Record.PRIO, required=False, min_value=0, max_value=65535)
    disabled = s.BooleanField(default=False)
    changed = s.DateTimeField(read_only=True, required=False)

    # noinspection PyMethodMayBeStatic
    def validate_name(self, attrs, source):
        if source in attrs:
            name = attrs[source]

            if name == '@':
                name = self.object.domain.name

            attrs[source] = name.lower()  # The record name must be always lower-cased (DB requirement)

        return attrs

    def validate(self, attrs):
        record = self.object

        try:
            run_record_validator(record.domain, attrs.get('type', record.type), attrs.get('name', record.name),
                                 attrs.get('content', record.content))
        except RecordValidationError as exc:
            self._errors = exc.message_dict

        return attrs

    def detail_dict(self, **kwargs):
        """Always include id and name"""
        dd = super(RecordSerializer, self).detail_dict(**kwargs)
        dd['id'] = self.object.id
        dd['name'] = self.object.name

        return dd
