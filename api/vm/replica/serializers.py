from django.utils.translation import ugettext_lazy as _
from frozendict import frozendict

from api import serializers as s
from api.vm.utils import get_nodes
from api.node.image.api_views import NodeImageView
from api.vm.define.vm_define_disk import DISK_ID_MIN, DISK_ID_MAX
from api.vm.define.serializers import validate_nic_tags
from api.vm.define.slave_vm_define import SlaveVmDefine
from vms.models import Node, SlaveVm


class DiskPoolDictField(s.BaseDictField):
    _key_field_class = s.IntegerField
    _key_field_params = frozendict(min_value=DISK_ID_MIN + 1, max_value=DISK_ID_MAX + 1)
    _val_field_class = s.CharField
    _val_field_params = frozendict(max_length=64)


class VmReplicaSerializer(s.InstanceSerializer):
    _model_ = SlaveVm
    _default_fields_ = ('repname',)
    _update_fields_ = ('reserve_resources', 'sleep_time', 'enabled', 'bwlimit')

    hostname = s.CharField(source='master_vm.hostname', read_only=True)
    repname = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', source='name', max_length=24, min_length=1)
    node = s.SlugRelatedField(slug_field='hostname', queryset=Node.objects, required=True)  # Updated only by POST
    root_zpool = s.CharField(max_length=64, required=False)  # Updated only by POST
    disk_zpools = DiskPoolDictField(required=False)  # Updated only by POST
    reserve_resources = s.BooleanField(default=True)  # Default value changed below during POST
    sleep_time = s.IntegerField(source='rep_sleep_time', min_value=0, max_value=86400, default=60)
    enabled = s.BooleanField(source='rep_enabled', default=True)
    bwlimit = s.IntegerField(source='rep_bwlimit', required=False, min_value=0, max_value=2147483647)
    last_sync = s.DateTimeField(read_only=True, required=False)
    reinit_required = s.BooleanField(source='rep_reinit_required', read_only=True, required=False)
    node_status = s.DisplayChoiceField(source='vm.node.status', choices=Node.STATUS_DB, read_only=True)
    created = s.DateTimeField(source="vm.created", read_only=True, required=False)

    def __init__(self, request, slave_vm, *args, **kwargs):
        self.img_required = None
        self.reserve_resources_changed = False
        self._detail_dict = {}

        super(VmReplicaSerializer, self).__init__(request, slave_vm, *args, **kwargs)

        if request.method == 'POST':
            vm = slave_vm.vm
            dc_settings = request.dc.settings
            self.fields['reserve_resources'].default = dc_settings.VMS_VM_REPLICA_RESERVATION_DEFAULT
            self.fields['node'].queryset = get_nodes(request, is_compute=True)
            self._disks = vm.json_get_disks()

            if vm.is_kvm():
                self.fields['disk_zpools'].max_items = len(self._disks)
            else:
                del self.fields['disk_zpools']
        else:
            self.fields['node'].required = False
            self.fields['node'].read_only = True
            self.fields['root_zpool'].read_only = True
            self.fields['disk_zpools'].read_only = True

    def validate_disk_zpools(self, attrs, source):
        """Basic disk_zpools validation (POST only)"""
        disk_zpools = attrs.get(source, None)

        if disk_zpools:
            if max(disk_zpools.keys()) > len(self._disks):
                raise s.ValidationError(_('Invalid disk_id.'))

        return attrs

    def validate_node(self, attrs, source):
        """Basic node validation (POST only)"""
        try:
            node = attrs[source]
        except KeyError:
            return attrs

        if node == self.object.node:
            raise s.ValidationError(_('Target node is the same as current node.'))

        if node.status != Node.ONLINE:
            raise s.ValidationError(_('Target node is not in online state.'))

        # Check nic tags
        try:
            validate_nic_tags(self.object.vm, new_node=node)
        except s.ValidationError:
            raise s.ValidationError(_('Some networks are not available on target node.'))

        return attrs

    def _validate_create(self, attrs):
        """Validate node storage zpools, resources, ... and create slave VM (POST only)"""
        node = attrs['node']
        self._detail_dict['node'] = node.hostname
        slave_vm = self.object
        slave_vm.set_rep_hostname()
        slave_vm.node = node
        slave_vm.reserve_resources = attrs.get('reserve_resources', True)
        slave_vm_define = SlaveVmDefine(slave_vm)

        # Validate root_zpool (we can do this after we know the new node)
        root_zpool = attrs.get('root_zpool', None)
        try:
            root_zpool = slave_vm_define.save_root_zpool(root_zpool)
        except s.APIValidationError as exc:
            self._errors['node'] = exc.api_errors
            return False
        else:
            if root_zpool:
                self._detail_dict['root_zpool'] = root_zpool

        # Validate disk_zpools (we can do this after we know the new node)
        if slave_vm.vm.is_kvm():
            disk_zpools = attrs.get('disk_zpools', {})
            try:
                disk_zpools = slave_vm_define.save_disk_zpools(disk_zpools)
            except s.APIValidationError as exc:
                self._errors['node'] = exc.api_errors
                return False
            else:
                if disk_zpools:
                    self._detail_dict['disk_zpools'] = disk_zpools

        # Validate dc_node resources
        try:
            slave_vm_define.validate_node_resources(ignore_cpu_ram=not slave_vm.reserve_resources)
        except s.APIValidationError as exc:
            self._errors['node'] = exc.api_errors
            return False

        # Validate storage resources
        try:
            slave_vm_define.validate_storage_resources()
        except s.APIValidationError as exc:
            self._errors['node'] = exc.api_errors
            return False

        # Validate images
        self.img_required = slave_vm_define.check_required_images()

        # noinspection PyAttributeOutsideInit
        self.slave_vm_define = slave_vm_define

        return True

    def _validate_update(self, attrs):
        """Validate node resources if reserve_resources changed to True"""
        try:
            reserve_resource = attrs['reserve_resources']
        except KeyError:
            pass
        else:
            # We need to know whether the user requested change of the reserve_resources attribute
            self.reserve_resources_changed = reserve_resource != self.object.reserve_resources

            if self.reserve_resources_changed and reserve_resource:
                slave_vm_define = SlaveVmDefine(self.object)

                try:
                    slave_vm_define.validate_node_resources(ignore_cpu_ram=False, ignore_disk=True)
                except s.APIValidationError as exc:
                    self._errors['node'] = exc.api_errors
                    return False

        return True

    def validate(self, attrs):
        if self.object.rep_reinit_required:
            raise s.ValidationError(_('Server replica requires re-initialization.'))

        if self.request.method == 'POST':
            total = SlaveVm.objects.filter(master_vm=self.object.master_vm).exclude(name=u'').count()
            self.object.rep_id = total + 1
            limit = self.request.dc.settings.VMS_VM_REPLICA_LIMIT

            if limit is not None:
                if int(limit) <= total:
                    raise s.ValidationError(_('Maximum number of server replicas reached.'))

            self._validate_create(attrs)
        else:  # PUT
            self._validate_update(attrs)

        return attrs

    def save_slave_vm(self):
        """Initial saving of slave VM - used only by POST vm_replica"""
        # The only difference between a slave and master VM should be the hostname
        # hence we change the slave hostname temporarily to the real hostname for the purpose of sync_json()
        slave_vm = self.object
        hostname = slave_vm.vm.hostname
        slave_vm.vm.hostname = slave_vm.master_vm.hostname
        slave_vm.vm.choose_vnc_port()
        slave_vm.vm.sync_json()
        slave_vm.vm.hostname = hostname

        # We also don't want to save the replication state (which can be only updated by vm_replica_cb)
        sync_status = slave_vm.sync_status
        slave_vm.sync_status = SlaveVm.DIS
        self.slave_vm_define.save()
        slave_vm.sync_status = sync_status

        return self.slave_vm_define.slave_vm

    def node_image_import(self):
        if self.img_required:
            ns, img = self.img_required
            return NodeImageView.import_for_vm(self.request, ns, img, self.object)
        return None

    def detail_dict(self, **kwargs):
        # noinspection PyStatementEffect
        self.data
        dd = super(VmReplicaSerializer, self).detail_dict(**kwargs)
        dd.update(self._detail_dict)
        dd['repname'] = self.object.name

        return dd
