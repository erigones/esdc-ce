from logging import getLogger

from django.utils.translation import ugettext_lazy as _
from django.db.models import Q

from api import serializers as s
from vms.models import DefaultDc, Node, Vm

logger = getLogger(__name__)

PERMISSION_DENIED = _('Permission denied.')


class AlertSerializer(s.Serializer):
    """
    Used by NodeHistoryView to validate zpools value.
    """
    since = s.TimeStampField(required=False)
    until = s.TimeStampField(required=False)
    last = s.IntegerField(required=False)
    vm_hostnames = s.ArrayField(required=False)
    vm_uuids = s.ArrayField(required=False)
    node_hostnames = s.ArrayField(required=False)
    node_uuids = s.ArrayField(required=False)
    show_events = s.BooleanField(default=True)
    dc_bound = s.BooleanField(default=True)

    def __init__(self, request, *args, **kwargs):
        super(AlertSerializer, self).__init__(*args, **kwargs)
        self.request = request
        self.vms = None  # This will be a list of VM uuids if vm_* filters are set
        self.nodes = None  # This will be a list of node uuids if node_* filters are set

    def validate_dc_bound(self, attrs, source):
        if not attrs.get(source) and not self.request.user.is_super_admin(self.request):
            raise s.ValidationError(PERMISSION_DENIED)

        return attrs

    def validate(self, attrs):
        request = self.request
        since = attrs.get('since', None)
        until = attrs.get('until', None)

        if until and not since:
            self._errors['since'] = s.ErrorList([_('Missing value.')])
            return attrs

        if since and not until:
            attrs['until'] = s.TimeStampField.now()

        dc_bound = attrs['dc_bound']
        vm_uuids = attrs.get('vm_uuids', None)
        vm_hostnames = attrs.get('vm_hostnames', None)
        node_uuids = attrs.get('node_uuids', None)
        node_hostnames = attrs.get('node_hostnames', None)

        if vm_hostnames is not None or vm_uuids is not None:
            vms_qs = Vm.objects.exclude(status=Vm.NOTCREATED).filter(slavevm__isnull=True)\
                       .filter(Q(hostname__in=vm_hostnames or ()) | Q(uuid__in=vm_uuids or ())).order_by('uuid')
        else:
            vms_qs = None

        if dc_bound:
            if node_uuids is not None:
                self._errors['node_uuids'] = s.ErrorList([PERMISSION_DENIED])
                return attrs

            if node_hostnames is not None:
                self._errors['node_hostnames'] = s.ErrorList([PERMISSION_DENIED])
                return attrs

            if vms_qs:
                self.vms = map(str, vms_qs.filter(dc=request.dc).values_list('uuid', flat=True))
        else:
            request.dc = DefaultDc()  # Warning: Changing request.dc
            logger.debug('"%s %s" user="%s" _changed_ dc="%s" permissions=%s', request.method, request.path,
                         request.user.username, request.dc.name, request.dc_user_permissions)

            if node_hostnames is not None or node_uuids is not None:
                qs = Node.objects.filter(Q(hostname__in=node_hostnames or ()) | Q(uuid__in=node_uuids or ()))
                self.nodes = qs.order_by('uuid').values_list('hostname', flat=True)

            if vms_qs:
                default_dc_zabbix_server = request.dc.settings.MON_ZABBIX_SERVER
                self.vms = [vm.uuid for vm in vms_qs.select_related('dc').only('uuid', 'dc').order_by('uuid')
                            if vm.dc.settings.MON_ZABBIX_SERVER == default_dc_zabbix_server]

        return attrs
