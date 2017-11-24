from django.utils.translation import ugettext_lazy as _

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
    show_all = s.BooleanField(default=False)

    def __init__(self, request, obj=None, instance=None, data=None, **kwargs):
        self.obj = obj
        self.request = request

        # We cannot set a function as a default argument of TimeStampField
        if data is None:
            data = {}
        else:
            data = data.copy()

        if 'since' in data and 'until' not in data:
            data['until'] = s.TimeStampField.now()

        super(AlertSerializer, self).__init__(instance=instance, data=data, **kwargs)

    def validate(self, attrs):
        show_all = attrs.get('show_all')

        if show_all and not self.request.user.is_super_admin(self.request):
            raise s.ValidationError(_('You don\'t have sufficient access rights to use show_all parameter.'))

        return attrs
