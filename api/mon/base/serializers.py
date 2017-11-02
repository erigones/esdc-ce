from api import serializers as s


class AlertSerializer(s.Serializer):
    """
    Used by NodeHistoryView to validate zpools value.
    """
    since = s.TimeStampField(required=False)
    until = s.TimeStampField(required=False)
    last = s.IntegerField(required=False)
    display_notes = s.BooleanField(default=True)
    display_items = s.BooleanField(default=True)
    hosts_or_groups = s.ArrayField(default=[])

    def __init__(self, obj=None, instance=None, data=None, **kwargs):
        self.obj = obj
        # We cannot set a function as a default argument of TimeStampField
        if data is None:
            data = {}
        else:
            data = data.copy()

        if 'since' in data and 'until' not in data:
            data['until'] = s.TimeStampField.now()

        super(AlertSerializer, self).__init__(instance=instance, data=data, **kwargs)
