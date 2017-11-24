from django.utils.translation import ugettext_lazy as _

from api import serializers as s
from vms.models import Vm


class AlertSerializer(s.Serializer):
    """
    Used by NodeHistoryView to validate zpools value.
    """
    since = s.TimeStampField(required=False)
    until = s.TimeStampField(required=False)
    last = s.IntegerField(required=False)
    hosts = s.ArrayField(default=[])
    groups = s.ArrayField(default=[])
    show_events = s.BooleanField(default=True)
    dc_unbound = s.BooleanField(default=False)

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
        dc_unbound = attrs.get('dc_unbound')
        hosts = attrs.get('hosts')

        if dc_unbound:
            if self.request.user.is_super_admin(self.request):
                allowed_hosts = []
            else:
                raise s.ValidationError(_('You don\'t have sufficient access rights to use show_all parameter.'))
        else:
            # set hosts_or_groups to hosts in this DC.
            vms = Vm.objects.filter(dc=self.request.dc)
            allowed_hosts = [vm.hostname for vm in vms]

        if hosts:
            # Check if hosts set by user is subset of allowed hosts
            for host in hosts:
                if host not in allowed_hosts and not dc_unbound:
                    raise s.ValidationError(_('You are trying to filter host that is not in you DC!'))
        else:
            attrs['hosts'] = allowed_hosts

        return attrs
