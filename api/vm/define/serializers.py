from logging import getLogger

from django.core.validators import RegexValidator
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from django.utils.six import iteritems
from django.core import validators
from django.conf import settings

from api.mon import MonitoringBackend
from gui.models import User
from vms.models import VmTemplate, Vm, Node, Image, Subnet, IPAddress, NodeStorage
from api import serializers as s
from api.decorators import catch_api_exception
from api.exceptions import APIError, ObjectAlreadyExists
from api.validators import validate_owner, validate_mdata, mod2_validator
from api.vm.utils import get_nodes, get_templates, get_images, get_subnets, get_zpools, get_owners
from api.vm.base.serializers import VmBaseSerializer
from api.dns.record.api_views import RecordView

PERMISSION_DENIED = _('Permission denied')
INVALID_HOSTNAMES = frozenset(['define', 'status', 'backup', 'snapshot'])
NIC_ALLOWED_IPS_MAX = 8

logger = getLogger(__name__)


def is_kvm(vm, data=None, prefix='', ostype=None):
    if vm:
        return vm.is_kvm()

    if data is not None:
        ostype = data.get(prefix + 'ostype', None)

    if ostype:
        try:
            return int(ostype) in Vm.KVM
        except (TypeError, ValueError):
            pass

    return True


def validate_zpool(request, name, node=None):
    try:
        qs = get_zpools(request)
        if node:
            return qs.select_related('storage').get(node=node, zpool=name)
        elif not qs.filter(zpool=name).exists():
            raise NodeStorage.DoesNotExist
    except NodeStorage.DoesNotExist:
        raise s.ValidationError(_('Storage with zpool=%s does not exist.') % name)

    return None


def validate_nic_tags(vm, new_node=None, new_net=None):
    """VM nic tags must exists on compute node before deploy - bug #chili-593"""
    if not new_node:
        new_node = vm.node

    node_nic_tags = set([nictag['name'] for nictag in new_node.nictags])
    vm_nic_tags = set([Subnet.objects.get(uuid=nic['network_uuid']).nic_tag for nic in vm.json_get_nics()])

    if new_net:
        vm_nic_tags.add(new_net.nic_tag)

    if not vm_nic_tags.issubset(node_nic_tags):
        raise s.ValidationError(_('Network is not available on compute node.'))

    return None


class VmDefineSerializer(VmBaseSerializer):
    uuid = s.CharField(read_only=True)
    hostname = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\.-]+[A-Za-z0-9]$', max_length=128, min_length=4)
    alias = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\.-]+[A-Za-z0-9]$', max_length=24, min_length=4, required=False)
    ostype = s.IntegerChoiceField(choices=Vm.OSTYPE, default=settings.VMS_VM_OSTYPE_DEFAULT)
    cpu_type = s.ChoiceField(choices=Vm.CPU_TYPE, default=settings.VMS_VM_CPU_TYPE_DEFAULT)
    vcpus = s.IntegerField(max_value=64, min_value=1)
    ram = s.IntegerField(max_value=524288, min_value=32)
    note = s.CharField(required=False)
    owner = s.SlugRelatedField(slug_field='username', queryset=User.objects, read_only=False, required=False)  # vv
    node = s.SlugRelatedField(slug_field='hostname', queryset=Node.objects, read_only=False, required=False)  # vv
    template = s.SlugRelatedField(slug_field='name', queryset=VmTemplate.objects, read_only=False, required=False)  # vv
    tags = s.TagField(required=False, default=[])  # null value checked in TagField
    monitored_internal = s.BooleanField(default=settings.MON_ZABBIX_ENABLED)
    monitored = s.BooleanField(default=settings.VMS_VM_MONITORED_DEFAULT)
    monitoring_hostgroups = s.ArrayField(max_items=16, default=[],
                                         validators=(
                                             RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS),))
    monitoring_templates = s.ArrayField(max_items=32, default=[])
    installed = s.BooleanField(default=False)
    snapshot_limit_manual = s.IntegerField(required=False)  # Removed from json if null, limits set below
    snapshot_size_limit = s.IntegerField(required=False)  # Removed from json if null, limits set below
    cpu_shares = s.IntegerField(default=settings.VMS_VM_CPU_SHARES_DEFAULT, min_value=0, max_value=1048576)
    zfs_io_priority = s.IntegerField(default=settings.VMS_VM_ZFS_IO_PRIORITY_DEFAULT, min_value=0, max_value=1024)
    zpool = s.CharField(default=Node.ZPOOL, max_length=64)
    resolvers = s.ArrayField(read_only=True)
    maintain_resolvers = s.BooleanField(default=True)  # OS only
    routes = s.RoutesField(default={})  # OS only
    vga = s.ChoiceField(choices=Vm.VGA_MODEL, default=settings.VMS_VGA_MODEL_DEFAULT)  # KVM only
    mdata = s.MetadataField(max_items=32, default=settings.VMS_VM_MDATA_DEFAULT,
                            validators=(validate_mdata(Vm.RESERVED_MDATA_KEYS),))
    locked = s.BooleanField(read_only=True, required=False)
    created = s.DateTimeField(read_only=True, required=False)

    def __init__(self, request, *args, **kwargs):
        self.request = request
        self.old_hostname = None
        self.hostname_changed = False
        self.zpool_changed = False
        self.node_changed = False
        self.update_node_resources = False
        self.update_storage_resources = []
        self.check_node_resources = kwargs.pop('check_node_resources', True)
        self.zone_img = None
        self.dc_settings = dc_settings = self.request.dc.settings
        hostname = kwargs.pop('hostname', None)
        data = kwargs.get('data', None)

        super(VmDefineSerializer, self).__init__(request, *args, **kwargs)
        self._is_kvm = kvm = is_kvm(self.object, data)

        if kvm:
            del self.fields['maintain_resolvers']
            del self.fields['routes']
        else:
            del self.fields['cpu_type']
            del self.fields['vga']

        if not kwargs.get('many', False):
            self.fields['owner'].default = request.user.username  # Does not work
            self.fields['ostype'].default = dc_settings.VMS_VM_OSTYPE_DEFAULT
            self.fields['zpool'].default = dc_settings.VMS_STORAGE_DEFAULT
            # noinspection PyProtectedMember
            self.fields['monitored_internal'].default = dc_settings.MON_ZABBIX_ENABLED \
                and dc_settings._MON_ZABBIX_VM_SYNC
            self.fields['monitored'].default = dc_settings.MON_ZABBIX_ENABLED and dc_settings.MON_ZABBIX_VM_SYNC \
                and dc_settings.VMS_VM_MONITORED_DEFAULT
            self.fields['cpu_shares'].default = dc_settings.VMS_VM_CPU_SHARES_DEFAULT
            self.fields['zfs_io_priority'].default = dc_settings.VMS_VM_ZFS_IO_PRIORITY_DEFAULT
            self.fields['owner'].queryset = get_owners(self.request)
            self.fields['template'].queryset = get_templates(self.request)
            self.fields['node'].queryset = get_nodes(self.request, is_compute=True)
            self.fields['mdata'].default = dc_settings.VMS_VM_MDATA_DEFAULT

            field_snapshot_limit_manual = self.fields['snapshot_limit_manual']
            field_snapshot_size_limit = self.fields['snapshot_size_limit']
            field_snapshot_limit_manual.default = dc_settings.VMS_VM_SNAPSHOT_LIMIT_MANUAL_DEFAULT
            field_snapshot_size_limit.default = dc_settings.VMS_VM_SNAPSHOT_SIZE_LIMIT_DEFAULT

            if dc_settings.VMS_VM_SNAPSHOT_LIMIT_MANUAL is None:
                min_snap, max_snap = 0, 65536
            else:
                min_snap, max_snap = 1, int(dc_settings.VMS_VM_SNAPSHOT_LIMIT_MANUAL)
                field_snapshot_limit_manual.required = field_snapshot_limit_manual.disallow_empty = True
            field_snapshot_limit_manual.validators.append(validators.MinValueValidator(min_snap))
            field_snapshot_limit_manual.validators.append(validators.MaxValueValidator(max_snap))

            if dc_settings.VMS_VM_SNAPSHOT_SIZE_LIMIT is None:
                min_snaps_size, max_snaps_size = 0, 2147483647
            else:
                min_snaps_size, max_snaps_size = 1, int(dc_settings.VMS_VM_SNAPSHOT_SIZE_LIMIT)
                field_snapshot_size_limit.required = field_snapshot_size_limit.disallow_empty = True
            field_snapshot_size_limit.validators.append(validators.MinValueValidator(min_snaps_size))
            field_snapshot_size_limit.validators.append(validators.MaxValueValidator(max_snaps_size))

            if kvm:
                self.fields['vga'].default = dc_settings.VMS_VGA_MODEL_DEFAULT

        # defaults
        if self.request.method == 'POST':
            self.fields['hostname'].default = hostname
            self.fields['alias'].default = hostname

            # defaults from template
            if data is not None and 'template' in data:
                try:
                    template = get_templates(self.request).get(name=str(data['template']))
                except VmTemplate.DoesNotExist:
                    pass  # this should be stopped by default validate_template
                else:
                    # ostype is in own column
                    if template.ostype is not None:
                        self.fields['ostype'].default = template.ostype
                    # all serializer attributes are in json['vm_define'] object
                    for field, value in template.vm_define.items():
                        try:
                            self.fields[field].default = value
                        except KeyError:
                            pass

    def restore_object(self, attrs, instance=None):
        if instance is not None:  # set (PUT)
            vm = instance
        else:  # create (POST)
            vm = Vm(dc=self.request.dc)

        # Set owner first (needed for hostname_is_valid_fqdn)
        if 'owner' in attrs and attrs['owner'] is not None:
            vm.owner = attrs['owner']

        # Cache old hostname in case we would change it
        vm.hostname_is_valid_fqdn()

        # Get json
        _json = vm.json

        # Datacenter settings
        dc_settings = vm.dc.settings

        # Json defaults must be set before template data
        if 'uuid' not in _json:
            _json.update2(dc_settings.VMS_VM_JSON_DEFAULTS.copy())
            _json['resolvers'] = dc_settings.VMS_VM_RESOLVERS_DEFAULT

        # First populate vm.json with template data, so they can be overridden by data specified by user
        if 'template' in attrs and attrs['template'] is not None:
            vm.template = attrs['template']
            _json.update2(vm.sync_template())
            data = vm.template.vm_define
        else:
            data = {}

        # Set json
        vm.json = _json

        # Mix template data with user attributes (which take precedence here)
        data.update(attrs)

        # ostype and brand must be set first
        if 'ostype' in data:
            vm.set_ostype(data.pop('ostype'))

        # Save user data
        for key, val in iteritems(data):
            if key == 'node':
                vm.set_node(val)
            elif key == 'tags':
                vm.set_tags(val)
            else:
                setattr(vm, key, val)

        # Default disk with image for non-global zone
        if instance is None and not vm.is_kvm() and 'image_uuid' not in vm.json:
            vm.save_item('image_uuid', self.zone_img.uuid, save=False)
            vm.save_item('quota', int(round(float(self.zone_img.size) / float(1024))), save=False)
            vm.save_item('zfs_root_compression', self.dc_settings.VMS_DISK_COMPRESSION_DEFAULT, save=False)

        return vm

    def validate_owner(self, attrs, source):
        """Cannot change owner while pending tasks exist"""
        validate_owner(self.object, attrs.get(source, None), _('VM'))

        return attrs

    def validate_node(self, attrs, source):
        # Changing compute nodes is not supported
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            # Only changing from None or in notcreated state is allowed
            if self.object and self.object.node:
                if self.object.node != value:
                    if self.object.is_notcreated():
                        self.node_changed = True
                    else:
                        raise s.ValidationError(_('Cannot change node.'))
            elif value is not None:
                self.node_changed = True

            if self.node_changed and value:
                if value.status != Node.ONLINE:
                    raise s.ValidationError(_('Node is currently not available.'))
                # Node changed to some existing node - check nic tags - bug #chili-593
                if self.object:
                    validate_nic_tags(self.object, new_node=value)

        return attrs

    def validate_hostname(self, attrs, source):
        # Changing the hostname is an invasive operation
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object and (self.object.hostname == value or self.object.uuid == value):
                pass  # Do not check if the same hostname or uuid was provided
            elif Vm.objects.filter(Q(hostname__iexact=value) | Q(uuid__iexact=value)).exists():
                raise ObjectAlreadyExists(model=Vm)
            elif '..' in value or '--' in value or value in INVALID_HOSTNAMES:
                raise s.ValidationError(s.WritableField.default_error_messages['invalid'])

            if self.object and self.object.hostname != value:
                self.old_hostname = self.object.hostname  # Used by info event
                self.hostname_changed = True  # Update DNS record

        return attrs

    def validate_template(self, attrs, source):
        # Check if template changed
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object and value and self.object.template != value:
                raise s.ValidationError(_('Cannot change template.'))

        return attrs

    def validate_cpu_shares(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if not self.request.user.is_staff and value != self.dc_settings.VMS_VM_CPU_SHARES_DEFAULT:
                raise s.ValidationError(PERMISSION_DENIED)

        return attrs

    def validate_zfs_io_priority(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if not self.request.user.is_staff and value != self.dc_settings.VMS_VM_ZFS_IO_PRIORITY_DEFAULT:
                raise s.ValidationError(PERMISSION_DENIED)

        return attrs

    def validate_zpool(self, attrs, source):
        # Just check if zpool changed
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object:
                if self.object.zpool == value:
                    return attrs
                if self.object.is_deployed():
                    raise s.ValidationError(_('Cannot change zpool.'))
                if not self.object.is_kvm():
                    raise s.ValidationError(_('Cannot change zpool for this OS type. '
                                              'Please change it on the first disk.'))

            self.zpool_changed = True

        return attrs

    def validate_ostype(self, attrs, source):
        # ostype cannot change
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object:
                if self.object.ostype != value:
                    raise s.ValidationError(_('Cannot change ostype.'))
            elif not is_kvm(self.object, ostype=value):
                # Creating zone -> Issue #chili-461 (must be enabled globally and in DC)
                if not (settings.VMS_ZONE_ENABLED and self.dc_settings.VMS_ZONE_ENABLED):
                    raise s.ValidationError(_('This OS type is not supported.'))
                # Creating zone -> check if default zone image is available
                if value == Vm.LINUX_ZONE:
                    default_zone_image = self.dc_settings.VMS_DISK_IMAGE_LX_ZONE_DEFAULT
                else:
                    default_zone_image = self.dc_settings.VMS_DISK_IMAGE_ZONE_DEFAULT

                zone_images = get_images(self.request, ostype=value)  # Linux Zone or SunOS Zone images ordered by name

                try:
                    self.zone_img = zone_images.get(name=default_zone_image)
                except Image.DoesNotExist:
                    self.zone_img = zone_images.first()

                if not self.zone_img:
                    raise s.ValidationError(_('Default disk image for this OS type is not available.'))

        return attrs

    def validate_monitored_internal(self, attrs, source):
        # Only SuperAdmin can change this attribute
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if not self.request.user.is_staff and value != self.fields['monitored_internal'].default:
                raise s.ValidationError(PERMISSION_DENIED)

        return attrs

    def validate_monitoring_hostgroups(self, attrs, source):
        # Allow to use only available hostgroups
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object and self.object.monitoring_hostgroups == value:
                return attrs
            elif self.dc_settings.MON_ZABBIX_HOSTGROUPS_VM_RESTRICT and not \
                    set(value).issubset(set(self.dc_settings.MON_ZABBIX_HOSTGROUPS_VM_ALLOWED)):
                raise s.ValidationError(_('Selected monitoring hostgroups are not available.'))

        return attrs

    def validate_monitoring_templates(self, attrs, source):
        # Allow to use only available templates
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object and self.object.monitoring_templates == value:
                return attrs
            elif self.dc_settings.MON_ZABBIX_TEMPLATES_VM_RESTRICT and not \
                    set(value).issubset(set(self.dc_settings.MON_ZABBIX_TEMPLATES_VM_ALLOWED)):
                raise s.ValidationError(_('Selected monitoring templates are not available.'))

        return attrs

    def validate_node_resources(self, attrs):
        vm = self.object
        dc = self.request.dc
        node = None
        node_errors = []

        # Check if there are free resources if node was set manually
        if self.node_changed:
            # No need to check if node really exists, because this check is
            # performed by the default serializer validation. But still it can be None...
            node = attrs['node']
            old_cpu = old_ram = new_disk = 0

            if vm:
                vm_disks = vm.get_disks()

                if node:  # We have a new node
                    # Get old resources
                    old_cpu, old_ram, new_disk = vm.get_cpu_ram_disk(zpool=node.zpool)

                    # Node changed to real node, validate storage names and disk space
                    for zpool, size in vm_disks.items():
                        # Also check if storage exists on this new node
                        try:
                            ns = validate_zpool(self.request, zpool, node=node)
                        except s.ValidationError as err:
                            node_errors.extend(err.messages)
                        else:
                            logger.info('Checking storage %s free space (%s) for vm %s', ns.storage, size, vm)
                            if ns.check_free_space(size):
                                self.update_storage_resources.append(ns)
                            else:
                                node_errors.append(_('Not enough free disk space on storage with zpool=%s.') % zpool)

                if vm.node:
                    # Node changed from real node -> always update storage resources associated with old node
                    self.update_storage_resources.extend(list(vm.node.get_node_storages(dc, vm_disks.keys())))

            if self._is_kvm:
                ram_overhead = settings.VMS_VM_KVM_MEMORY_OVERHEAD
            else:
                ram_overhead = 0

            # Use new or old absolute resource counts
            new_cpu = attrs.get('vcpus', old_cpu)
            new_ram = attrs.get('ram', old_ram) + ram_overhead

        # Also check for additional free resources if number of vcpus or ram
        # changed and node was set in the past (=> we stay on current node)
        elif vm and vm.node and ('ram' in attrs or 'vcpus' in attrs):
            node = vm.node
            old_cpu, old_ram = vm.get_cpu_ram()
            new_cpu = attrs.get('vcpus', old_cpu) - old_cpu
            new_ram = attrs.get('ram', old_ram) - old_ram
            new_disk = 0  # Disk size vs. node was validated in vm_define_disk

        # At this point we have to check for resources if node is defined
        if node:
            dc_node = node.get_dc_node(dc)
            # noinspection PyUnboundLocalVariable
            logger.info('Checking node=%s, dc_node=%s resources (cpu=%s, ram=%s, disk=%s) for vm %s',
                        node, dc_node, new_cpu, new_ram, new_disk, vm)

            if new_cpu > 0 and not dc_node.check_free_resources(cpu=new_cpu):
                node_errors.append(_('Not enough free vCPUs on node.'))

            if new_ram > 0 and not dc_node.check_free_resources(ram=new_ram):
                node_errors.append(_('Not enough free RAM on node.'))

            if new_disk > 0 and not dc_node.check_free_resources(disk=new_disk):
                node_errors.append(_('Not enough free disk space on node.'))

            if node_errors:
                self._errors['node'] = s.ErrorList(node_errors)
            else:
                self.update_node_resources = True

    def validate(self, attrs):
        vm = self.object

        try:
            ostype = attrs['ostype']
        except KeyError:
            ostype = vm.ostype

        # Default cpu_type for a new Windows VM is 'host'
        if not vm and ostype == Vm.WINDOWS and 'cpu_type' not in self.init_data:
            attrs['cpu_type'] = Vm.CPU_TYPE_HOST

        # Check if template ostype matches vm.ostype
        template = attrs.get('template', None)

        if template and template.ostype:
            if template.ostype != ostype:
                err = _('Server template is only available for servers with "%(ostype)s" OS type.')
                self._errors['template'] = s.ErrorList([err % {'ostype': template.get_ostype_display()}])

        # Default owner is request.user, but setting this in __init__ does not work
        if 'owner' in attrs and attrs['owner'] is None:
            if vm:
                del attrs['owner']
            else:
                attrs['owner'] = self.request.user

        # Zpool check depends on node
        if self.zpool_changed or self.node_changed:
            try:
                zpool = attrs['zpool']
            except KeyError:
                zpool = vm.zpool
            try:
                node = attrs['node']
            except KeyError:
                if vm:
                    node = vm.node
                else:
                    node = None
            try:
                validate_zpool(self.request, zpool, node=node)
            except s.ValidationError as err:
                self._errors['zpool'] = err.messages

        # Check if alias is unique for this user
        if 'alias' in attrs:
            if vm and 'owner' not in attrs:
                owner = vm.owner
            elif 'owner' in attrs:
                owner = attrs['owner']
            else:
                owner = self.request.user

            alias = attrs['alias']
            if vm and vm.alias == alias:
                pass  # Do not check if the same alias was provided
            elif Vm.objects.filter(dc=self.request.dc, owner=owner, alias__iexact=alias).exists():
                self._errors['alias'] = s.ErrorList([_('This server name is already in use. '
                                                       'Please supply a different server name.')])

        # Check if there are free resources if node is set/changed and/or ram/vcpus changed
        if not self._errors:  # already invalid serializer, skip complicated resource checking
            self.validate_node_resources(attrs)

        # Disable monitored flag if monitoring module/sync disabled
        dc_settings = self.dc_settings

        # noinspection PyProtectedMember
        if 'monitored_internal' in attrs and not (dc_settings.MON_ZABBIX_ENABLED and dc_settings._MON_ZABBIX_VM_SYNC):
            attrs['monitored_internal'] = False

        if 'monitored' in attrs and not (dc_settings.MON_ZABBIX_ENABLED and dc_settings.MON_ZABBIX_VM_SYNC):
            attrs['monitored'] = False

        return attrs


class _VmDefineDiskSerializer(s.Serializer):
    size = s.IntegerField(max_value=268435456, min_value=1)
    boot = s.BooleanField(default=False)  # Needed for server list in GUI (both KVM and ZONE)
    compression = s.ChoiceField(choices=Vm.DISK_COMPRESSION, default=settings.VMS_DISK_COMPRESSION_DEFAULT)
    zpool = s.CharField(default=Node.ZPOOL, max_length=64)
    block_size = s.IntegerField(min_value=512, max_value=131072, validators=(mod2_validator,))  # Default set below

    def __init__(self, request, vm, *args, **kwargs):
        # custom stuff
        self.vm = vm
        self.request = request
        self.update_node_resources = False
        self.update_storage_resources = []
        self.zpool_changed = False
        self.node_storage = None
        self.disk_id = kwargs.pop('disk_id', None)
        self.img = None
        self.img_old = None
        self.img_error = False

        if len(args) > 0:  # PUT, GET
            # rewrite disk data
            if isinstance(args[0], list):
                data = map(self.fix_before, args[0])
            else:
                data = self.fix_before(args[0])
            super(_VmDefineDiskSerializer, self).__init__(data, *args[1:], **kwargs)

        else:  # POST
            super(_VmDefineDiskSerializer, self).__init__(*args, **kwargs)
            data = kwargs.get('data', None)
            # defaults disk size from image
            if data is not None and 'image' in data and data['image']:
                try:
                    self.img = get_images(self.request).get(name=data['image'])
                except Image.DoesNotExist:
                    self.img_error = True  # this should be stopped by default validate_image
                else:
                    self.fields['size'].default = self.img.size
                    if vm.is_kvm():
                        self.fields['refreservation'].default = self.img.size

            if vm.is_kvm() and data is not None and 'size' in data:
                self.fields['refreservation'].default = data['size']

            if self.disk_id == 0:
                self.fields['boot'].default = True

        dc_settings = vm.dc.settings
        self.fields['block_size'].default = Vm.DISK_BLOCK_SIZE[vm.ostype]
        self.fields['zpool'].default = vm.zpool
        self.fields['compression'].default = dc_settings.VMS_DISK_COMPRESSION_DEFAULT

        # Set defaults from template
        if self.disk_id is not None and vm.template:
            for field, value in vm.template.get_vm_define_disk(self.disk_id).items():
                try:
                    self.fields[field].default = value
                except KeyError:
                    pass

    def fix_before(self, data):
        """
        Rewrite disk data from json to serializer compatible object.
        """
        if 'image_uuid' in data:
            try:
                self.img = self.img_old = Image.objects.get(uuid=data['image_uuid'])
                data['image'] = self.img.name
            except Image.DoesNotExist:
                raise APIError(detail='Unknown image in disk definition.')
            else:
                del data['image_uuid']

        return data

    @property
    def jsondata(self):
        """
        Rewrite validated disk data from user to json usable data.
        """
        data = dict(self.object)

        if 'image' in data:
            image_name = data.pop('image')

            if image_name:  # got valid image, let's replace it with image_uuid
                data['image_uuid'] = str(self.img.uuid)
                data['image_size'] = self.img.size  # needed for valid json

                if self.vm.is_kvm():
                    data.pop('block_size', None)  # block size is inherited from the image
            else:  # remove image from json
                data.pop('image_uuid', None)
                data.pop('image_size', None)

        return data

    def detail_dict(self, **kwargs):
        ret = super(_VmDefineDiskSerializer, self).detail_dict(**kwargs)
        ret.pop('disk_id', None)  # disk_id is added in the view

        return ret

    def validate_boot(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if value is True and self.disk_id is not None:
                if self.disk_id != 0:
                    raise s.ValidationError(_('Cannot set boot flag on disks other than first disk.'))

                other_disks = self.vm.json_get_disks()
                if other_disks:
                    try:
                        del other_disks[self.disk_id]
                    except IndexError:
                        pass

                    for d in other_disks:
                        if d['boot'] is True:
                            raise s.ValidationError(_('Cannot set boot flag on multiple disks.'))

        return attrs

    def validate_image(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.img_error:
                raise s.ObjectDoesNotExist(value)

            if not value:
                value = attrs[source] = None

            if value and self.disk_id != 0:
                raise s.ValidationError(_('Cannot set image on disks other than first disk.'))

            if self.object:
                if (self.img and self.img.name == value) or (self.img == value):
                    return attrs  # Input image name is the same as in DB
                elif self.vm.is_notcreated():
                    if value:
                        try:
                            self.img = get_images(self.request).get(name=value)
                        except Image.DoesNotExist:
                            raise s.ObjectDoesNotExist(value)
                    else:
                        self.img = None
                else:
                    raise s.ValidationError(_('Cannot change disk image.'))
            elif value and self.vm.is_deployed():
                raise s.ValidationError(_('Cannot set disk image on already created server.'))

            if self.img:
                if self.img.access in Image.UNUSABLE or self.img.ostype != self.vm.ostype:
                    raise s.ObjectDoesNotExist(value)
                if self.img.status != Image.OK:
                    raise s.ValidationError(_('Image is currently not available.'))

        return attrs

    def validate_zpool(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object:
                old_zpool = self.object.get('zpool')
                if old_zpool == value:
                    return attrs
                if self.vm.is_deployed():
                    raise s.ValidationError(_('Cannot change zpool.'))
            else:
                old_zpool = value  # never-mind that this is actually a new zpool (see validate_storage_resources())

            self.node_storage = validate_zpool(self.request, value, node=self.vm.node)
            self.zpool_changed = old_zpool

        return attrs

    def validate_storage_resources(self, zpool, size):
        """Check storage or node resources"""
        if not self.vm.node:
            return

        if self.object and not self.zpool_changed:  # only size has changed
            new_size = size - self.object.get('size')
        else:
            new_size = size  # size or zpool changed or new disk

        if not new_size:
            return

        vm = self.vm
        ns = self.get_node_storage(zpool, vm.node)

        logger.info('Checking storage %s free space (%s) for vm %s', ns.storage, new_size, vm)
        if ns.check_free_space(new_size):
            # NodeStorage for update:
            self.update_storage_resources.append(ns)
            # Old NodeStorage for update
            if self.zpool_changed:
                self.update_storage_resources.append(vm.node.get_node_storage(vm.dc, self.zpool_changed))
        else:
            self._errors['size'] = s.ErrorList([_('Not enough free disk space on storage.')])

        if zpool == vm.node.zpool:
            dc_node = vm.node.get_dc_node(vm.dc)
            logger.info('Checking node %s resources (disk=%s) for vm %s', vm.node, new_size, vm)
            if dc_node.check_free_resources(disk=new_size):
                self.update_node_resources = True
            else:
                self._errors['size'] = s.ErrorList([_('Not enough free disk space on node.')])

    def validate(self, attrs):
        try:
            size = attrs['size']
            size_change = True
        except KeyError:
            size = self.object['size']
            size_change = False

        try:
            zpool = attrs['zpool']
        except KeyError:
            zpool = self.object['zpool']

        if self.vm.is_kvm() and self.img:  # always check size if image
            if not self.img.resize and size != self.img.size:
                self._errors['size'] = s.ErrorList([_('Cannot define disk size other than image size (%s), '
                                                      'because image does not support resizing.') % self.img.size])
            elif size < self.img.size:
                self._errors['size'] = s.ErrorList([_('Cannot define smaller disk size than '
                                                      'image size (%s).') % self.img.size])

            if self.vm.is_notcreated():
                # Check disk_driver in image manifest (bug #chili-605) only if server is not created;
                # User should be able to change the driver after server is deployed
                img_disk_driver = self.img.json.get('manifest', {}).get('disk_driver', None)
                if img_disk_driver:
                    try:
                        model = attrs['model']
                    except KeyError:
                        model = self.object['model']
                    if img_disk_driver != model:
                        self._errors['image'] = s.ErrorList([_('Disk image requires specific disk '
                                                               'model (%s).') % img_disk_driver])

        if self.vm.is_kvm():
            try:
                refreservation = attrs['refreservation']
            except KeyError:  # self.object must exist here (PUT)
                try:
                    refreservation = self.object['refreservation']
                except KeyError:
                    refreservation = attrs['refreservation'] = size
                else:
                    if refreservation > 0:
                        refreservation = attrs['refreservation'] = size  # Override refreservation with new disk size

            if refreservation > size:
                self._errors['refreservation'] = s.ErrorList([_('Cannot define refreservation larger than disk size.')])

        if not self._errors and (size_change or self.zpool_changed) and (self.vm.is_kvm() or self.disk_id == 0):
            self.validate_storage_resources(zpool, size)

        return attrs

    @property
    def data(self):
        if self._data is None:
            data = super(_VmDefineDiskSerializer, self).data

            if self.many:
                for i, disk in enumerate(data):
                    disk['disk_id'] = i + 1
            else:
                data['disk_id'] = self.disk_id
                try:
                    data['disk_id'] += 1
                except TypeError:
                    pass

            self._data = data

        return self._data

    def get_node_storage(self, zpool, node):
        if not self.node_storage and node:
            self.node_storage = node.get_node_storage(self.vm.dc, zpool)
        return self.node_storage


class KVmDefineDiskSerializer(_VmDefineDiskSerializer):
    model = s.ChoiceField(choices=Vm.DISK_MODEL, default=settings.VMS_DISK_MODEL_DEFAULT)
    image = s.CharField(required=False, default=settings.VMS_DISK_IMAGE_DEFAULT, max_length=64)
    refreservation = s.IntegerField(default=0, max_value=268435456, min_value=0)  # default set below

    # nocreate = s.BooleanField(default=False)  # processed in save_disks()

    def __init__(self, request, vm, *args, **kwargs):
        super(KVmDefineDiskSerializer, self).__init__(request, vm, *args, **kwargs)
        dc_settings = vm.dc.settings
        self.fields['model'].default = dc_settings.VMS_DISK_MODEL_DEFAULT
        self.fields['image'].default = dc_settings.VMS_DISK_IMAGE_DEFAULT

    def validate_block_size(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object and self.vm.is_deployed() and self.object.get('block_size') != value:
                raise s.ValidationError(_('Cannot change block_size.'))

        return attrs


class ZVmDefineDiskSerializer(_VmDefineDiskSerializer):
    image = s.CharField(required=True, default=settings.VMS_DISK_IMAGE_ZONE_DEFAULT, max_length=64)

    def __init__(self, request, vm, *args, **kwargs):
        super(ZVmDefineDiskSerializer, self).__init__(request, vm, *args, **kwargs)
        if vm.ostype == Vm.LINUX_ZONE:
            self.fields['image'].default = vm.dc.settings.VMS_DISK_IMAGE_LX_ZONE_DEFAULT
        else:
            self.fields['image'].default = vm.dc.settings.VMS_DISK_IMAGE_ZONE_DEFAULT

        if self.disk_id > 0:
            if not self.object:
                self.object = {}
            self.object['boot'] = False
            self.object['image'] = None
            self.object['size'] = vm.json.get('quota', 0) * 1024
            self.object['zpool'] = vm.json.get('zpool', Node.ZPOOL)
            self.fields['image'].read_only = True
            self.fields['size'].read_only = True
            self.fields['zpool'].read_only = True
            self.fields['boot'].read_only = True
        elif self.disk_id is not None:
            self.object['boot'] = True
            self.fields['boot'].read_only = True


# noinspection PyPep8Naming
def VmDefineDiskSerializer(request, vm, *args, **kwargs):
    if vm.is_kvm():
        return KVmDefineDiskSerializer(request, vm, *args, **kwargs)
    else:
        return ZVmDefineDiskSerializer(request, vm, *args, **kwargs)


class VmDefineNicSerializer(s.Serializer):
    mac = s.MACAddressField(required=False)  # processed in save_nics()
    model = s.ChoiceField(choices=Vm.NIC_MODEL, default=settings.VMS_NIC_MODEL_DEFAULT)
    net = s.CharField()
    ip = s.IPAddressField(required=False)  # checked in validate()
    netmask = s.IPAddressField(read_only=True)
    gateway = s.IPAddressField(read_only=True)
    primary = s.BooleanField(default=False)
    dns = s.BooleanField(default=False)  # Should we set DNS records for this IP?
    use_net_dns = s.BooleanField(default=False)  # set VM resolvers from Subnet?
    allow_dhcp_spoofing = s.BooleanField(default=False)
    allow_ip_spoofing = s.BooleanField(default=False)
    allow_mac_spoofing = s.BooleanField(default=False)
    allow_restricted_traffic = s.BooleanField(default=False)
    allow_unfiltered_promisc = s.BooleanField(default=False)
    allowed_ips = s.IPAddressArrayField(default=list(), max_items=NIC_ALLOWED_IPS_MAX)
    monitoring = s.BooleanField(default=False)
    set_gateway = s.BooleanField(default=True)

    def __init__(self, request, vm, *args, **kwargs):
        self.request = request
        self.vm = vm
        self.dc_settings = dc_settings = vm.dc.settings
        self.nic_id = kwargs.pop('nic_id', None)
        self.resolvers = vm.resolvers
        # List of DNS Record objects, where the content is equal to this NIC's IP address
        self._dns = []
        # Subnet object currently set in this NIC
        self._net = None
        # New Subnet object that is going to be replaced by self._net
        self._net_old = None
        # The self._ip attribute holds the IPAddress object that is currently associated with this NIC
        # In case the related network object has dhcp_passthrough=True the value of self._ip will be False.
        self._ip = None
        # self._ip_old holds the IPAddress object which is currently associated with this NIC, but is going to be
        # changed by a new IP (self._ip). The purpose of this attribute is to clean up old DNS and IP relations after
        # the VM is updated (save_ip()).
        self._ip_old = None
        # The self._ips and self._ips_old have the same purpose as self._ip and self._ip_old but in relation to
        # the allowed_ips array.
        self._ips = ()
        self._ips_old = ()
        # Helper attribute for self.save_ip()
        self._changing_allowed_ips = False
        # This attribute is True if vm.monitoring_ip equals to nic['ip']
        self._monitoring_old = None

        if len(args) > 0:  # GET, PUT
            # rewrite nic data
            if isinstance(args[0], list):
                data = map(self.fix_before, args[0])
            else:
                data = self.fix_before(args[0])
            super(VmDefineNicSerializer, self).__init__(data, *args[1:], **kwargs)
        else:  # POST
            super(VmDefineNicSerializer, self).__init__(*args, **kwargs)

        # By default set DNS for the first NIC
        if self.nic_id == 0:
            self.fields['dns'].default = True
            self.fields['primary'].default = True

        # By default enable monitoring for this NIC according to VMS_NIC_MONITORING_DEFAULT
        if self.nic_id == dc_settings.VMS_NIC_MONITORING_DEFAULT - 1:
            self.fields['monitoring'].default = True

        # Set defaults from template
        if self.nic_id is not None and vm.template:
            for field, value in vm.template.get_vm_define_nic(self.nic_id).items():
                try:
                    self.fields[field].default = value
                except KeyError:
                    pass

        if vm.is_kvm():
            self.fields['model'].default = dc_settings.VMS_NIC_MODEL_DEFAULT
        else:
            del self.fields['model']

    def fix_before(self, data):
        """
        Rewrite nic data from json to serializer compatible object.
        """
        # fetch Subnet object
        if data.get('network_uuid', None):
            try:
                self._net = Subnet.objects.get(uuid=data['network_uuid'])
                data['net'] = self._net.name
            except Subnet.DoesNotExist:
                raise APIError(detail='Unknown net in NIC definition.')
            else:
                del data['network_uuid']
        else:
            data['net'] = None

        # default vlan ID is 0
        if 'vlan_id' not in data:
            data['vlan_id'] = 0

        # primary does not exist in json if False
        if 'primary' not in data:
            data['primary'] = False

        ip = data.get('ip', None)

        # fetch IPAddress object
        if ip:
            try:
                if self._net and self._net.dhcp_passthrough and ip == 'dhcp':
                    # No netmask/gateway in json, only ip with 'dhcp' value
                    data['ip'] = ip = None  # ip=None means that monitoring (below) will be False
                    data['netmask'] = None
                    data['gateway'] = None
                    self._ip = False
                else:
                    self._ip = IPAddress.objects.get(ip=ip, subnet=self._net)
            except IPAddress.DoesNotExist:
                raise APIError(detail='Unknown ip in NIC definition.')

        allowed_ips = data.get('allowed_ips', None)

        if allowed_ips is not None:
            self._ips = IPAddress.objects.filter(ip__in=allowed_ips, subnet=self._net)
            data['allowed_ips'] = list(set(allowed_ips))

        # dns is True if a valid DNS A record exists and points this NICs IP
        data['dns'] = False
        if ip and self.vm.hostname_is_valid_fqdn():  # will return False if DNS_ENABLED is False
            dns = RecordView.Record.get_records_A(self.vm.hostname, self.vm.fqdn_domain)

            if dns:
                for record in dns:
                    if record.content == ip:
                        self._dns.append(record)
                        data['dns'] = True

        if self._net and self._net.get_resolvers() == self.vm.resolvers:
            data['use_net_dns'] = True
        else:
            data['use_net_dns'] = False

        # monitoring is true if vm.monitoring_ip equals to nic['ip']
        self._monitoring_old = self.vm.monitoring_ip == ip
        if self._monitoring_old:
            data['monitoring'] = True
        else:
            data['monitoring'] = False

        # set_gateway is True if gateway is set
        data['set_gateway'] = bool(data.get('gateway', None))

        return data

    @property
    def jsondata(self):
        """
        Rewrite validated nic data from user to json usable data.
        """
        data = dict(self.object)

        if 'net' in data:
            subnet = data.pop('net')
            if subnet:  # got valid subnet, let's replace it with network_uuid
                data['network_uuid'] = str(self._net.uuid)

        # Remove dummy attributes
        data.pop('dns', None)
        data.pop('use_net_dns', None)
        data.pop('monitoring', None)
        data.pop('set_gateway', None)

        if not data.get('ip') and self._net.dhcp_passthrough:
            data['ip'] = 'dhcp'
            data.pop('netmask', None)
            data.pop('gateway', None)

        return data

    def detail_dict(self, **kwargs):
        ret = super(VmDefineNicSerializer, self).detail_dict(**kwargs)
        ret.pop('nic_id', None)  # nic_id is added in the view

        # When changing net or ip (PUT), the IP address may not be in the detail dict
        if self._net_old or self._ip_old is not None:
            ret['ip'] = self.object.get('ip', None)
            ret['netmask'] = self.object.get('netmask', None)
            ret['gateway'] = self.object.get('gateway', None)
            ret['allowed_ips'] = self.object.get('allowed_ips', [])

        return ret

    def validate_mac(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object and self.vm.is_deployed():
                if not value or self.object.get('mac', None) != value:
                    raise s.ValidationError(_('Cannot change MAC address.'))

        return attrs

    def validate_set_gateway(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object and self.vm.is_deployed() and self.object.get('set_gateway', None) != value:
                raise s.ValidationError(_('Cannot change gateway.'))

        return attrs

    def _validate_insecure_boolean_attr(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            return attrs

        if not self.request.user.is_staff and value:
            raise s.ValidationError(PERMISSION_DENIED)

        return attrs

    def validate_allow_dhcp_spoofing(self, attrs, source):
        return self._validate_insecure_boolean_attr(attrs, source)  # Only SuperAdmin can enable this option

    def validate_allow_ip_spoofing(self, attrs, source):
        return self._validate_insecure_boolean_attr(attrs, source)  # Only SuperAdmin can enable this option

    def validate_allow_mac_spoofing(self, attrs, source):
        return self._validate_insecure_boolean_attr(attrs, source)  # Only SuperAdmin can enable this option

    def validate_allow_restricted_traffic(self, attrs, source):
        return self._validate_insecure_boolean_attr(attrs, source)  # Only SuperAdmin can enable this option

    def validate_allow_unfiltered_promisc(self, attrs, source):
        return self._validate_insecure_boolean_attr(attrs, source)  # Only SuperAdmin can enable this option

    def validate_primary(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if value is True and self.nic_id is not None:
                other_nics = self.vm.json_get_nics()

                if other_nics:
                    try:
                        del other_nics[self.nic_id]
                    except IndexError:
                        pass

                    for n in other_nics:
                        if n.get('primary', False) is True:
                            raise s.ValidationError(_('Cannot enable primary flag on multiple NICs.'))

        return attrs

    def validate_net(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if value:
                if self.object and self._net and self._net.name == value:
                    return attrs  # Input net name is the same as in DB
                try:
                    _net = get_subnets(self.request).get(name=value)
                except Subnet.DoesNotExist:
                    raise s.ObjectDoesNotExist(value)
                else:
                    if _net.access in Subnet.UNUSABLE:
                        raise s.ObjectDoesNotExist(value)

                    if self.vm.node:  # New network and node is defined - check nic tags - bug #chili-593
                        validate_nic_tags(self.vm, new_net=_net)

                    if self.object and self._net != _net:  # changing net is tricky, see validate() below
                        self._net_old = self._net
                    self._net = _net

        return attrs

    def _check_ip_usage(self, ipaddress, allowed_ips=False):
        """Returns an error message if IP address is used by some VM"""
        ip = ipaddress.ip

        if ipaddress.usage == IPAddress.VM_REAL and ipaddress.vm == self.vm:  # Trying to re-use our lost IP?
            if ipaddress.ip in self.vm.json_get_ips():  # check if selected address is not on another interface
                return _('Object with name=%s is already used.') % ip
        else:
            if ipaddress.vm is not None:  # check if selected address is free in this subnet
                return _('Object with name=%s is already used as default address.') % ip

            if allowed_ips:
                if ipaddress.usage not in (IPAddress.VM, IPAddress.VM_REAL):  # check if selected IP can be used for VM
                    return _('Object with name=%s is not available.') % ip

                for other_vm in ipaddress.vms.exclude(uuid=self.vm.uuid):
                    if other_vm.dc != self.vm.dc:
                        return _('Object with name=%s is already used as additional address in '
                                 'another virtual datacenter.') % ip
            else:
                if ipaddress.usage != IPAddress.VM:  # check if selected address can be used for virtual servers
                    return _('Object with name=%s is not available.') % ip

                if ipaddress.vms.exists():  # IP address is already used as allowed_ips
                    return _('Object with name=%s is already used as additional address.') % ip

        return None

    def validate(self, attrs):
        net = self._net
        assert net

        # first fetch the IPAddress object
        if 'ip' in attrs and attrs['ip']:  # ip specified
            ip = attrs['ip']

            if self.object and not self._net_old and self._ip and self._ip.ip == ip:
                pass  # Input IP is the same as in DB
            else:
                try:  # check if selected address exists in subnet
                    _ip = IPAddress.objects.get(ip=ip, subnet=net)
                except IPAddress.DoesNotExist:
                    self._errors['ip'] = s.ObjectDoesNotExist(ip).messages
                    return attrs
                else:
                    error = self._check_ip_usage(_ip)

                    if error:
                        self._errors['ip'] = s.ErrorList([error])
                        return attrs

                    if self._ip and self._ip != _ip:  # changing ip is tricky
                        self._ip_old = self._ip

                    self._ip = _ip
                    attrs['ip'] = self._ip.ip  # normalize IP address

        else:
            # changing net + ip not specified || empty ip specified (finding new ip below)
            if self._net_old or not attrs.get('ip', True):
                self._ip_old = self._ip
                self._ip = None

        allowed_ips = list(set(attrs.get('allowed_ips', [])))

        if allowed_ips:
            _ips = IPAddress.objects.filter(ip__in=allowed_ips, subnet=net)

            if self.object and not self._net_old and self._ips and self._ips == _ips:
                pass  # Input allowed_ips are the same as in DB
            else:
                ip_list = _ips.values_list('ip', flat=True)

                if len(ip_list) != len(allowed_ips):
                    self._errors['allowed_ips'] = s.ErrorList(
                        [_('Object with name=%s does not exist.') % i for i in allowed_ips if i not in ip_list]
                    )
                    return attrs

                if self._ip and self._ip.ip in allowed_ips:
                    self._errors['allowed_ips'] = s.ErrorList(
                        [_('The default IP address must not be among allowed_ips.')]
                    )
                    return attrs

                errors = [err for err in (self._check_ip_usage(ipaddress, allowed_ips=True) for ipaddress in _ips)
                          if err is not None]

                if errors:
                    self._errors['allowed_ips'] = s.ErrorList(errors)
                    return attrs

                if self._ips and self._ips != _ips:  # changing allowed_ips is tricky
                    # noinspection PyUnresolvedReferences
                    self._ips_old = self._ips.exclude(ip__in=ip_list)

                self._ips = _ips
                self._changing_allowed_ips = True
                attrs['allowed_ips'] = list(set(ip_list))
        else:
            # changing net + allowed_ips not specified, but already set on nic (with old net)
            # or settings empty allowed_ips (=> user wants to remove allowed_ips)
            if self._ips and (self._net_old or 'allowed_ips' in attrs):
                attrs['allowed_ips'] = list()
                self._ips_old = self._ips
                self._ips = ()
                self._changing_allowed_ips = True

        if net.dhcp_passthrough:
            # no dns and monitoring for this NIC
            try:
                dns = attrs['dns']
            except KeyError:
                dns = self.object['dns']

            try:
                monitoring = attrs['monitoring']
            except KeyError:
                monitoring = self.object['monitoring']

            if dns or monitoring:
                if dns:
                    self._errors['dns'] = s.ErrorList([_('Cannot enable DNS for externally managed network.')])

                if monitoring:
                    self._errors['monitoring'] = s.ErrorList([_('Cannot enable monitoring for externally '
                                                                'managed network.')])

                return attrs

        # try to get free ip address for this subnet
        if not self._ip:
            if net.dhcp_passthrough:
                # no IP for this NIC
                self._ip = False
                attrs['ip'] = None
                attrs['netmask'] = None
                attrs['gateway'] = None
            else:
                try:
                    self._ip = IPAddress.objects.filter(subnet=net, vm__isnull=True, vms=None, usage=IPAddress.VM)\
                                                .exclude(ip__in=allowed_ips).order_by('?')[0:1].get()
                except IPAddress.DoesNotExist:
                    raise s.ValidationError(_('Cannot find free IP address for net %s.') % net.name)
                else:
                    logger.info('IP address %s for NIC ID %s on VM %s was chosen automatically',
                                self._ip, self.nic_id, self.vm)
                    attrs['ip'] = self._ip.ip  # set ip

        if self._ip is not False:
            assert self._ip and attrs.get('ip', True)
            # other attributes cannot be specified (they need to be inherited from net)
            attrs['netmask'] = net.netmask
            attrs['gateway'] = net.gateway

        # get set_gateway from new or existing NIC object
        try:
            set_gateway = attrs['set_gateway']
        except KeyError:
            set_gateway = self.object['set_gateway']

        if not set_gateway:
            # Set gateway to None even if the NIC must not have any gateway set (see Vm._NICS_REMOVE_EMPTY)
            attrs['gateway'] = None

        # These attributes cannot be specified (they need to be inherited from net)
        attrs['nic_tag'] = net.nic_tag
        attrs['vlan_id'] = net.vlan_id

        if 'use_net_dns' in attrs:
            if attrs['use_net_dns']:
                self.resolvers = net.get_resolvers()
            elif self.object:
                self.resolvers = self.dc_settings.VMS_VM_RESOLVERS_DEFAULT

        return attrs

    @staticmethod
    @catch_api_exception
    def save_a(request, task_id, vm, ip, dns=(), delete=False):
        if not vm.dc.settings.DNS_ENABLED:
            logger.info('DNS support disabled: skipping DNS A record saving for vm %s', vm)
            return None

        # Find domain and check if the domain is legit for creating A records
        if not vm.hostname_is_valid_fqdn():
            logger.warn('Valid domain for vm %s not found. Could not %s DNS A record.',
                        vm, 'delete' if delete else 'add')
            return None

        record_cls = RecordView.Record
        ip = str(ip.ip)
        domain = vm.fqdn_domain
        logger.info('%s DNS A record for vm %s, domain %s, name %s.',
                    'Deleting' if delete else 'Adding/Updating', vm, domain, ip)

        if not dns:
            dns = record_cls.get_records_A(vm.hostname, domain)

        if delete:
            method = 'DELETE'
            data = {}
        else:
            records_exist = [record.content == ip for record in dns]

            if records_exist and all(records_exist):
                logger.info('DNS A record for vm %s, domain %s, name %s already exists.', vm, domain, ip)
                return True

            if len(dns):
                method = 'PUT'
                data = {'content': ip}
            else:
                method = 'POST'
                dns = (record_cls(domain=RecordView.internal_domain_get(domain, task_id=task_id)),)
                data = {
                    'type': record_cls.A,
                    'name': vm.hostname.lower(),
                    'domain': domain,
                    'content': ip,
                }

        for record in dns:
            RecordView.internal_response(request, method, record, data, task_id=task_id, related_obj=vm)

        return True

    @staticmethod
    @catch_api_exception
    def save_ptr(request, task_id, vm, ip, net, delete=False, content=None):
        dc_settings = vm.dc.settings

        if not dc_settings.DNS_ENABLED:
            logger.info('DNS support disabled: skipping DNS PTR record saving for vm %s', vm)
            return None

        record_cls = RecordView.Record
        ipaddr = str(ip.ip)
        ptr = record_cls.get_record_PTR(ipaddr)
        logger.info('%s DNS PTR record for vm %s, domain %s, name %s.',
                    'Deleting' if delete else 'Adding', vm, net.ptr_domain, ipaddr)

        def default_ptr(server, ip_address):
            placeholders = {
                'hostname': server.hostname,
                'alias': server.alias,
                'ipaddr': ip_address.replace('.', '-'),
            }

            try:
                return dc_settings.DNS_PTR_DEFAULT.format(**placeholders)
            except (KeyError, ValueError, TypeError) as e:
                logger.error('Could not convert DNS_PTR_DEFAULT (%s) for IP %s of VM %s. Error was: %s',
                             dc_settings.DNS_PTR_DEFAULT, ip_address, server, e)
                return 'ptr-{ipaddr}.example.com'.format(**placeholders)

        if ptr:
            if delete:
                method = 'DELETE'
                data = {}
            else:
                method = 'PUT'
                data = {'content': content or default_ptr(vm, ipaddr)}
        else:
            if delete:
                return None
            else:
                ptr = record_cls(domain=RecordView.internal_domain_get(net.ptr_domain, task_id=task_id))
                method = 'POST'
                data = {
                    'type': record_cls.PTR,
                    'domain': net.ptr_domain,
                    'name': record_cls.get_reverse(ipaddr),
                    'content': content or default_ptr(vm, ipaddr),
                }

        return RecordView.internal_response(request, method, ptr, data, task_id=task_id, related_obj=vm)

    @staticmethod
    def _remove_vm_ip_association(vm, ip, many=False):
        logger.info('Removing association of IP %s with vm %s.', ip, vm)

        if ip.usage == IPAddress.VM_REAL and vm.is_deployed():  # IP is set on hypervisor
            logger.info(' ^ Removal of association of IP %s with vm %s will be delayed until PUT vm_manage is done.',
                        ip, vm)
        else:  # DB only operation
            if many:
                ip.vms.remove(vm)
            else:
                ip.vm = None
                ip.save()

    @staticmethod
    def _create_vm_ip_association(vm, ip, many=False):
        logger.info('Creating association of IP %s with vm %s.', ip, vm)

        if ip.vm:
            raise APIError(detail='Unexpected problem with IP address association.')

        if many:
            ip.vms.add(vm)
        else:
            ip.vm = vm
            ip.save()

    @classmethod
    def _update_vm_ip_association(cls, vm, ip, delete=False, many=False):
        if delete:
            cls._remove_vm_ip_association(vm, ip, many=many)
        else:
            cls._create_vm_ip_association(vm, ip, many=many)

    def save_ip(self, task_id, delete=False, update=False):
        vm = self.vm
        ip = self._ip
        ip_old = self._ip_old

        if ip is False:  # means that the new IP uses a network with dhcp_passthrough
            assert self._net.dhcp_passthrough
        else:
            assert ip

        if not update or ip_old:
            if ip_old:
                self._remove_vm_ip_association(vm, ip_old)

            if ip:
                self._update_vm_ip_association(vm, ip, delete=delete)

            # Delete PTR Record for old IP
            if ip_old and ip_old.subnet.ptr_domain:
                self.save_ptr(self.request, task_id, vm, ip_old, ip_old.subnet, delete=True)  # fails silently

            # Create PTR Record only if a PTR domain is defined
            if ip and self._net and self._net.ptr_domain:
                self.save_ptr(self.request, task_id, vm, ip, self._net, delete=delete)  # fails silently

        if self._changing_allowed_ips:
            for _ip_old in self._ips_old:
                self._remove_vm_ip_association(vm, _ip_old, many=True)

            for _ip in self._ips:
                self._update_vm_ip_association(vm, _ip, delete=delete, many=True)

        # Create DNS A Record if dns setting is True
        # or Remove dns if dns settings was originally True, but now is set to False
        dns = self.object['dns']
        remove_dns = self._dns and not dns

        if dns or remove_dns:
            if remove_dns:
                delete = True

            if delete and ip_old:
                # The dns should be removed for the old ip
                ip = ip_old

            if ip:
                self.save_a(self.request, task_id, vm, ip, dns=self._dns, delete=delete)

        return ip

    def update_ip(self, task_id):
        return self.save_ip(task_id, update=True)

    def delete_ip(self, task_id):
        return self.save_ip(task_id, delete=True)

    @property
    def data(self):
        if self._data is None:
            data = super(VmDefineNicSerializer, self).data

            if self.many:
                for i, nic in enumerate(data):
                    nic['nic_id'] = i + 1
            else:
                data['nic_id'] = self.nic_id
                try:
                    data['nic_id'] += 1
                except TypeError:
                    pass

            self._data = data

        return self._data

    def get_monitoring_ip(self, delete=False):
        # Return ip if monitoring is True,
        # empty string if monitoring was true, but now is set to False or delete was requested,
        # or None if monitoring_ip should stay unchanged
        monitoring = self.object['monitoring']
        ip = self.object['ip']

        if self._ip is False:
            assert self._net.dhcp_passthrough
            assert not monitoring
        else:
            assert self._ip

        if self._monitoring_old and (delete or not monitoring):
            logger.info('Removing monitoring IP %s for vm %s.', ip, self.vm)
            return ''
        elif monitoring:
            logger.info('Saving monitoring IP %s for vm %s.', ip, self.vm)
            return ip
        else:
            return None
