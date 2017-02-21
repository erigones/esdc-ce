from api import serializers as s


class MonHistorySerializer(s.Serializer):
    """
    Base class for validating monitoring history request data.
    """
    since = s.TimeStampField(required=False)
    until = s.TimeStampField(required=False)
    autorefresh = s.BooleanField(default=False)
    item_id = None

    def __init__(self, obj=None, instance=None, data=None, **kwargs):
        self.obj = obj
        # We cannot set a function as a default argument of TimeStampField
        if data is None:
            data = {}
        else:
            data = data.copy()
        if 'since' not in data:
            data['since'] = s.TimeStampField.one_hour_ago()
        if 'until' not in data:
            data['until'] = s.TimeStampField.now()
        super(MonHistorySerializer, self).__init__(instance=instance, data=data, **kwargs)
