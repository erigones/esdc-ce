from api import serializers as s


class MonNodeHistorySerializer(s.Serializer):
    """
    Used by mon_node_history to validate time period input.
    """
    since = s.TimeStampField(required=False)
    until = s.TimeStampField(required=False)
    autorefresh = s.BooleanField(default=False)

    def __init__(self, instance=None, data=None, **kwargs):
        # We cannot set a function as a default argument of TimeStampField - bug #chili-478 #note-10
        if data is None:
            data = {}
        else:
            data = data.copy()
        if 'since' not in data:
            data['since'] = s.TimeStampField.one_hour_ago()
        if 'until' not in data:
            data['until'] = s.TimeStampField.now()
        super(MonNodeHistorySerializer, self).__init__(instance=instance, data=data, **kwargs)
