from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _

from api import serializers as s
from api.mon import MonitoringBackend
from api.mon.serializers import MonHistorySerializer
from api.vm.define.serializers import VmDefineSerializer
from api.vm.define.vm_define_disk import DISK_ID_MIN, DISK_ID_MAX
from api.vm.define.vm_define_nic import NIC_ID_MIN, NIC_ID_MAX
from vms.models import Vm


class VmMonitoringSerializer(s.InstanceSerializer):
    """
    Serializer for validating mon_vm_define parameters.
    """
    _model_ = Vm
    _blank_fields_ = ('ip',)
    _update_fields_ = ('ip', 'dns', 'port', 'useip', 'proxy', 'templates', 'hostgroups')

    hostname = s.CharField(read_only=True)
    uuid = s.CharField(read_only=True)
    monitored = s.BooleanField(read_only=True)
    ip = s.IPAddressField(source='monitoring_ip', required=False)
    dns = s.RegexField(r'^[A-Za-z0-9\.-]+$', source='monitoring_dns', required=False, min_length=1, max_length=128)
    port = s.IntegerField(source='monitoring_port', required=False, min_value=1, max_value=65535)
    useip = s.BooleanField(source='monitoring_useip', required=False)
    proxy = s.CharField(source='monitoring_proxy', required=False, min_length=1, max_length=128)
    templates = s.ArrayField(source='monitoring_templates', max_items=32, required=False, default=[])
    hostgroups = s.ArrayField(source='monitoring_hostgroups', max_items=16, required=False, default=[],
                              validators=(RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS),))

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
    validate_templates = VmDefineSerializer.validate_monitoring_templates

    # Allow to use only available hostgroups
    validate_hostgroups = VmDefineSerializer.validate_monitoring_hostgroups


class NetworkVmMonHistorySerializer(MonHistorySerializer):
    """
    Used by VmHistoryView to validate nic_id value.
    """
    nic_id = s.IntegerField(required=True, min_value=NIC_ID_MIN + 1, max_value=NIC_ID_MAX + 1)

    def validate(self, attrs):
        nic_id = attrs.get('nic_id')
        assert nic_id

        try:
            self.item_id = self.obj.get_real_nic_id(self.obj.json_active_get_nics()[nic_id - 1])
        except IndexError:
            raise s.ValidationError(_('NIC ID not defined on VM.'))

        return attrs


class DiskVmMonHistorySerializer(MonHistorySerializer):
    """
    Used by VmHistoryView to validate disk_id value.
    """
    disk_id = s.IntegerField(required=True, min_value=DISK_ID_MIN + 1, max_value=DISK_ID_MAX + 1)

    def validate(self, attrs):
        disk_id = attrs.get('disk_id')
        assert disk_id

        try:
            self.item_id = disk_id - 1  # KVM IO templates are using "array_disk_id"
            self.obj.get_real_disk_id(self.obj.json_active_get_disks()[self.item_id])
        except IndexError:
            raise s.ValidationError(_('Disk ID not defined on VM.'))

        return attrs
