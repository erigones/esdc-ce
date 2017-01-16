from api import serializers as s
from api.vm.define.serializers import VmDefineSerializer
from vms.models import Vm


class VmMonitoringSerializer(s.InstanceSerializer):
    """
    Serializer for validating mon_vm_define parameters.
    """
    _model_ = Vm
    _blank_fields_ = ('ip',)
    _update_fields_ = ('ip', 'dns', 'port', 'useip', 'proxy', 'templates', 'hostgroups')

    hostname = s.CharField(read_only=True)
    monitored = s.BooleanField(read_only=True)
    ip = s.IPAddressField(source='monitoring_ip', required=False)
    dns = s.RegexField(r'^[A-Za-z0-9\.-]+$', source='monitoring_dns', required=False, min_length=1, max_length=128)
    port = s.IntegerField(source='monitoring_port', required=False, min_value=1, max_value=65535)
    useip = s.BooleanField(source='monitoring_useip', required=False)
    proxy = s.CharField(source='monitoring_proxy', required=False, min_length=1, max_length=128)
    templates = s.ArrayField(source='monitoring_templates', max_items=32, required=False, default=[])
    hostgroups = s.ArrayField(source='monitoring_hostgroups', max_items=16, required=False, default=[])

    def __init__(self, request, vm, *args, **kwargs):
        super(VmMonitoringSerializer, self).__init__(request, vm, *args, **kwargs)
        self.dc_settings = dc_settings = request.dc.settings
        self.fields['dns'].default = vm.hostname
        self.fields['port'].default = dc_settings.MON_ZABBIX_HOST_VM_PORT
        self.fields['useip'].default = dc_settings.MON_ZABBIX_HOST_VM_USEIP
        self.fields['proxy'].default = dc_settings.MON_ZABBIX_HOST_VM_PROXY

    def validate_useip(self, attrs, source):
        # null value will remove the useip parameter in monitoring_useip property => the default value will be used
        if source in attrs and self.init_data.get('useip', True) is None:
            attrs[source] = None

        return attrs

    # Allow to use only available templates
    validate_templates = VmDefineSerializer.validate_monitoring_templates.im_func

    # Allow to use only available hostgroups
    validate_hostgroups = VmDefineSerializer.validate_monitoring_hostgroups.im_func


class MonVmHistorySerializer(s.Serializer):
    """
    Used by mon_vm_history to validate time period input.
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
        super(MonVmHistorySerializer, self).__init__(instance=instance, data=data, **kwargs)
