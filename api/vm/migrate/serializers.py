from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist

from api import serializers as s
from api.serializers import APIValidationError
from api.vm.utils import get_nodes
from api.node.image.api_views import NodeImageView
from api.vm.define.vm_define_disk import DISK_ID_MIN, DISK_ID_MAX
from api.vm.define.serializers import validate_nic_tags
from api.vm.define.slave_vm_define import SlaveVmDefine
from api.dc.utils import get_dcs
from vms.models import Node, Dc, DcNode, SlaveVm
from pdns.models import Domain


MIN_PLATFORM_VERSION_LIVE_MIGRATION = 20171124


class DiskPoolDictField(s.BaseDictField):
    _key_field = s.IntegerField(min_value=DISK_ID_MIN + 1, max_value=DISK_ID_MAX + 1)
    _val_field = s.CharField(max_length=64)


class VmMigrateSerializer(s.Serializer):
    node = s.SlugRelatedField(slug_field='hostname', queryset=Node.objects, required=False)
    root_zpool = s.CharField(max_length=64, required=False)
    disk_zpools = DiskPoolDictField(required=False)
    live = s.BooleanField(default=False)

    def __init__(self, request, vm, *args, **kwargs):
        self.img_required = None
        self.request = request
        self.vm = vm

        super(VmMigrateSerializer, self).__init__(*args, **kwargs)
        self.fields['node'].queryset = get_nodes(request, is_compute=True)
        self._disks = vm.json_active_get_disks()
        self._live = False

        if vm.is_kvm():
            self.fields['disk_zpools'].max_items = len(self._disks)
        else:
            del self.fields['disk_zpools']

    def validate_disk_zpools(self, attrs, source):
        disk_zpools = attrs.get(source, None)

        if disk_zpools:
            if max(disk_zpools.keys()) > len(self._disks):
                raise s.ValidationError(_('Invalid disk_id.'))

        return attrs

    def validate_node(self, attrs, source):
        """Basic node validation"""
        node = attrs.get(source, None)

        if not node:
            attrs.pop(source, None)
            return attrs

        vm = self.vm

        if node == vm.node:
            raise s.ValidationError(_('Target node is the same as current node.'))

        if node.status != Node.ONLINE:
            raise s.ValidationError(_('Target node is not in online state.'))

        # Check nic tags
        try:
            validate_nic_tags(vm, new_node=node)
        except s.ValidationError:
            raise s.ValidationError(_('Some networks are not available on target node.'))

        return attrs

    def validate_live(self, attrs, source):
        value = attrs.get(source, None)

        if value:
            self._live = True

            if not self.vm.is_kvm():
                raise s.ValidationError(_('Live migration is currently available only for KVM.'))

        return attrs

    def validate(self, attrs):
        vm = self.vm
        node = attrs.get('node', vm.node)
        changing_node = attrs.get('node', vm.node) != vm.node

        if self._live:
            if not changing_node:
                self._errors['live'] = s.ErrorList([_('Live migration cannot be performed locally.')])
                return attrs

            if (node.platform_version_short < MIN_PLATFORM_VERSION_LIVE_MIGRATION or
                    vm.node.platform_version_short < MIN_PLATFORM_VERSION_LIVE_MIGRATION):
                self._errors['live'] = s.ErrorList([_('Source and/or target node platform does not '
                                                      'support live migration.')])
                return attrs

        # Ghost VM is a copy of a VM used to take up place in DB.
        # When node is changing we have to have all disks in a ghost VM.
        # When changing only disk pools, only the changed disks have to be in a ghost VM.
        ghost_vm = SlaveVm(_master_vm=vm)
        ghost_vm.reserve_resources = changing_node
        ghost_vm.set_migration_hostname()
        ghost_vm.node = node
        ghost_vm_define = SlaveVmDefine(ghost_vm)

        # Validate root_zpool (we can do this after we know the new node)
        root_zpool = attrs.get('root_zpool', None)
        # Every pool must be validated when changing node
        try:
            root_zpool = ghost_vm_define.save_root_zpool(root_zpool, save_same_zpool=changing_node)
        except APIValidationError as exc:
            self._errors['node'] = exc.api_errors
            return attrs

        # Validate disk_zpools (we can do this after we know the new node)
        if ghost_vm.vm.is_kvm():
            disk_zpools = attrs.get('disk_zpools', {})
            try:
                disk_zpools = ghost_vm_define.save_disk_zpools(disk_zpools, save_same_zpool=changing_node)
            except APIValidationError as exc:
                self._errors['node'] = exc.api_errors
                return attrs
        else:
            disk_zpools = {}

        # Nothing changed, he?
        if not changing_node and not (root_zpool or disk_zpools):
            raise s.ValidationError(_('Nothing to do.'))

        # Validate dc_node resources
        try:
            ghost_vm_define.validate_node_resources(ignore_cpu_ram=not changing_node)
        except APIValidationError as exc:
            self._errors['node'] = exc.api_errors
            return attrs

        # Validate storage resources
        try:
            ghost_vm_define.validate_storage_resources()
        except APIValidationError as exc:
            self._errors['node'] = exc.api_errors
            return attrs

        # Validate images
        self.img_required = ghost_vm_define.check_required_images()

        # Save params
        # noinspection PyAttributeOutsideInit
        self._root_zpool = root_zpool
        # noinspection PyAttributeOutsideInit
        self._disk_zpools = disk_zpools
        # noinspection PyAttributeOutsideInit
        self.ghost_vm_define = ghost_vm_define
        # noinspection PyAttributeOutsideInit
        self.changing_node = changing_node

        return attrs

    def save_ghost_vm(self):
        self.ghost_vm_define.save()
        return self.ghost_vm_define.slave_vm

    def node_image_import(self):
        if self.img_required:
            ns, img = self.img_required
            return NodeImageView.import_for_vm(self.request, ns, img, self.vm)
        return None

    @property
    def esmigrate_cmd(self):
        """Create esmigrate command"""
        vm = self.vm
        get_json = 'vmadm get %s 2>/dev/null' % vm.uuid
        params = []

        if self.changing_node:
            node = self.object['node']
            params.append('-H %s' % node.address)
            ssh = 'ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no ' \
                  '-o GSSAPIKeyExchange=no -o GSSAPIAuthentication=no -o LogLevel=QUIET -l root'
            get_json = '%s %s "%s"' % (ssh, node.address, get_json)

            if vm.is_kvm():
                params.append('-C %s' % self.ghost_vm_define.vm.vnc_port)

        if self._live:
            params.append('-L')

        if self._root_zpool:
            params.append('-p %s' % self._root_zpool)

        if self._disk_zpools:
            for n, zpool in self._disk_zpools.items():
                n -= 1
                params.append('-%s %s' % (n, zpool))

        return 'esmigrate migrate %s %s >&2; ' % (vm.uuid, ' '.join(params)) + get_json

    def detail_dict(self, **kwargs):
        dd = {'live': self._live}

        if self.changing_node:
            dd['node'] = self.object['node'].hostname

        if self._root_zpool:
            dd['root_zpool'] = self._root_zpool

        if self._disk_zpools:
            dd['disk_zpools'] = self._disk_zpools

        return dd


class VmDcSerializer(s.Serializer):
    """
    Validate target DC for VM.
    """
    target_dc = s.SlugRelatedField(slug_field='name', queryset=Dc.objects)

    def __init__(self, request, vm, *args, **kwargs):
        self.request = request
        self.vm = vm
        self.dc = None
        self.nss = None
        super(VmDcSerializer, self).__init__(*args, **kwargs)
        self.fields['target_dc'].queryset = get_dcs(request)

    def validate_target_dc(self, attrs, source):  # noqa: R701
        new_dc = attrs.get(source, None)

        if not new_dc:
            return attrs

        vm = self.vm

        if not vm.node:
            raise s.ValidationError(_('VM has no compute node assigned.'))

        if vm.dc == new_dc:
            raise s.ValidationError(_('Target datacenter is the same as current datacenter.'))

        # Check node
        try:
            new_dc_node = vm.node.get_dc_node(new_dc)
            old_dc_node = vm.node.get_dc_node(vm.dc)
        except ObjectDoesNotExist:
            raise s.ValidationError(_('VM compute node is not available in target datacenter.'))

        # Check node storages
        self.nss = nss = vm.get_node_storages()

        for ns in nss:
            if not ns.dc.filter(pk=new_dc.pk).exists():
                raise s.ValidationError(_('VM disk storages are not available in target datacenter.'))

        # Check domain
        if vm.hostname_is_valid_fqdn():
            try:
                new_dc.domaindc_set.get(domain_id=Domain.get_domain_id(vm.fqdn_domain))
            except ObjectDoesNotExist:
                raise s.ValidationError(_('VM domain is not available in target datacenter.'))

        # Check templates
        if vm.template and not new_dc.vmtemplate_set.filter(id=vm.template.id).exists():
            raise s.ValidationError(_('VM template is not available in target datacenter.'))

        # Check images
        vm_disks = vm.json_get_disks() + vm.json_active_get_disks()
        vm_images = set([dsk['image_uuid'] for dsk in vm_disks if 'image_uuid' in dsk])

        if vm_images and new_dc.image_set.filter(uuid__in=vm_images).distinct().count() != len(vm_images):
            raise s.ValidationError(_('VM disk image is not available in target datacenter.'))

        # Check networks
        vm_nics = vm.json_get_nics() + vm.json_active_get_nics()
        vm_networks = set([nic['network_uuid'] for nic in vm_nics if 'network_uuid' in nic])

        if vm_networks and new_dc.subnet_set.filter(uuid__in=vm_networks).distinct().count() != len(vm_networks):
            raise s.ValidationError(_('VM NIC networks are not available in target datacenter.'))

        # Check backup definition nodes and storages (pools)
        vm_bkpdefs = vm.backupdefine_set.all()
        vm_bkp_nodes = set([bd.node.uuid for bd in vm_bkpdefs])
        vm_bkp_zpools = set([bd.zpool.id for bd in vm_bkpdefs])

        if vm_bkp_nodes:
            new_dc_bkp_nodes_count = new_dc.node_set.filter(uuid__in=vm_bkp_nodes).values_list('uuid', flat=True)\
                                                                                  .distinct().count()
            if new_dc_bkp_nodes_count != len(vm_bkp_nodes):
                raise s.ValidationError(_('VM backup node is not available in target datacenter.'))

            new_dc_bkp_zpools_count = new_dc.nodestorage_set.filter(id__in=vm_bkp_zpools).values_list('id', flat=True)\
                                                                                         .distinct().count()
            if new_dc_bkp_zpools_count != len(vm_bkp_zpools):
                raise s.ValidationError(_('VM backup storage is not available in target datacenter.'))

        # Check free resources only when dealing with RESERVED strategies on target or source DcNode
        if new_dc_node.strategy == DcNode.RESERVED or old_dc_node.strategy == DcNode.RESERVED:
            vm_resources = vm.get_cpu_ram_disk(zpool=vm.node.zpool, ram_overhead=True)

            if not new_dc_node.check_free_resources(*vm_resources):
                raise s.ValidationError(_('Not enough free compute node resources in target datacenter.'))

        # Save new DC
        self.dc = new_dc

        return attrs
