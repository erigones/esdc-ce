from collections import defaultdict
from django.conf import settings
# noinspection PyProtectedMember
from django.core.cache import caches
from django.core.exceptions import SuspiciousOperation
from django.db import models
from django.db.models import Q, NOT_PROVIDED
from django.utils import timezone
from django.utils.six import iteritems
# noinspection PyUnresolvedReferences
from django.utils.six.moves import xrange
from django.utils.translation import ugettext_noop, ugettext_lazy as _
from frozendict import frozendict
from taggit.managers import TaggableManager
from taggit.models import TaggedItemBase
from types import NoneType
from uuid import uuid4, UUID

from vms.utils import SortedPickleDict
from vms.models.fields import CommaSeparatedUUIDField
# noinspection PyProtectedMember
from vms.models.base import _JsonPickleModel, _StatusModel, _OSType, _HVMType, _UserTasksModel
from vms.models.utils import pair_keys_to_items, diff_dict, diff_dict_nested
from vms.models.dc import Dc
from vms.models.node import Node
from vms.models.vmtemplate import VmTemplate
from gui.models import User


cache = caches['redis']
redis = cache.master_client


class TagVm(TaggedItemBase):
    content_object = models.ForeignKey('vms.Vm')

    class Meta:
        app_label = 'vms'
        verbose_name = _('Server Tag')
        verbose_name_plural = _('Server Tags')


def is_disk(disk, pool):
    x = 'size' in disk or 'image_uuid' in disk
    if pool:
        return x and disk.get('zpool', Node.ZPOOL) == pool
    return x


def is_ip(nic):
    ip = nic.get('ip', None)
    return ip and ip != 'dhcp'


class Vm(_StatusModel, _JsonPickleModel, _OSType, _HVMType, _UserTasksModel):
    """
    VM (guest) object.
    """
    # BRAND = (
    #     ('hvm', 'hvm'),
    #     ('kvm', 'kvm'),
    #     ('bhyve', 'bhyve'),
    #     ('joyent', 'joyent'),
    #     ('joyent-minimal', 'joyent-minimal'),
    #     ('sngl', 'sngl'),
    #     ('lx', 'lx'),
    # )

    HVM_TYPE_BRAND = frozendict({
        _HVMType.Hypervisor_KVM: 'kvm',
        _HVMType.Hypervisor_BHYVE: 'bhyve',
        _HVMType.Hypervisor_NONE: 'none',
    })

    OSTYPE_BRAND = frozendict({
        _OSType.LINUX: 'hvm',
        _OSType.SUNOS: 'hvm',
        _OSType.BSD: 'hvm',
        _OSType.WINDOWS: 'hvm',
        _OSType.SUNOS_ZONE: settings.VMS_VM_BRAND_SUNOS_ZONE_DEFAULT,
        _OSType.LINUX_ZONE: settings.VMS_VM_BRAND_LX_ZONE_DEFAULT,
    })

    CPU_TYPE_QEMU = 'qemu64'
    CPU_TYPE_HOST = 'host'
    CPU_TYPE = (
        (CPU_TYPE_QEMU, CPU_TYPE_QEMU),
        (CPU_TYPE_HOST, CPU_TYPE_HOST),
    )

    DISK_MODEL = (
        ('virtio', 'virtio'),
        ('ide', 'ide'),
        ('scsi', 'scsi'),
    )

    DISK_COMPRESSION = (
        ('off', 'off'),
        ('lzjb', 'lzjb'),
        ('gzip', 'gzip'),
        ('gzip-1', 'gzip-1'),
        ('gzip-2', 'gzip-2'),
        ('gzip-3', 'gzip-3'),
        ('gzip-4', 'gzip-4'),
        ('gzip-5', 'gzip-5'),
        ('gzip-6', 'gzip-6'),
        ('gzip-7', 'gzip-7'),
        ('gzip-8', 'gzip-8'),
        ('gzip-9', 'gzip-9'),
        ('zle', 'zle'),
        ('lz4', 'lz4'),
    )

    NIC_MODEL = (
        ('virtio', 'virtio'),
        ('e1000', 'e1000'),
        ('rtl8139', 'rtl8139'),
    )

    VGA_MODEL = (
        ('std', 'std'),
        ('cirrus', 'cirrus'),
        ('vmware', 'vmware'),
    )

    PENDING = 0  # no real, used only for status changes, not saved in DB
    STOPPED = 1
    RUNNING = 2
    STOPPING = 3
    NOTREADY = 7  # disk is not ready (maybe a rollback or migration or update/delete is in progress)
    FROZEN = 8  # stopped and cannot be started
    NOTCREATED = 9
    UNKNOWN = 10  # node is offline, not saved in DB
    CREATING = 11  # notcreated -> stopped
    DEPLOYING_START = 12  # stopped -> running -> stopped
    DEPLOYING_FINISH = 13  # stopped -> running
    DEPLOYING_DUMMY = 14  # notcreated -> stopped
    NOTREADY_STOPPED = 71
    NOTREADY_RUNNING = 72
    NOTREADY_FROZEN = 78
    NOTREADY_NOTCREATED = 79
    ERROR = 99  # Something went terribly wrong -> manual intervention is needed
    STATUS = (
        (STOPPED, ugettext_noop('stopped')),
        (RUNNING, ugettext_noop('running')),
        (STOPPING, ugettext_noop('stopping')),
        (NOTREADY, ugettext_noop('notready')),
        (CREATING, ugettext_noop('deploying')),
        (DEPLOYING_START, ugettext_noop('deploying')),
        (DEPLOYING_FINISH, ugettext_noop('deploying')),
        (DEPLOYING_DUMMY, ugettext_noop('deploying')),
        (FROZEN, ugettext_noop('frozen')),
        (NOTCREATED, ugettext_noop('notcreated')),
        (NOTREADY_STOPPED, ugettext_noop('stopped-')),
        (NOTREADY_RUNNING, ugettext_noop('running-')),
        (NOTREADY_FROZEN, ugettext_noop('frozen-')),
        (NOTREADY_NOTCREATED, ugettext_noop('notcreated-')),
        (ERROR, ugettext_noop('error')),
    )

    STATUS_DICT = frozendict({  # states on Node
        'stopped': STOPPED,
        'running': RUNNING,
        'stopping': STOPPING,
        'installed': STOPPED,
    })
    STATUS_UNUSED = frozenset([  # not useful states on Node (255)
        'ready',
        'shutting_down',
        'incomplete',
        'configured',
        'down',
        'provisioning',
        'receiving',
        'failed',
    ])
    STATUS_PENDING = ugettext_noop('pending')
    STATUS_UNKNOWN = ugettext_noop('unknown')
    STATUS_KNOWN = frozenset([STOPPED, STOPPING, RUNNING, NOTCREATED, ERROR])
    STATUS_OPERATIONAL = frozenset([RUNNING, STOPPED, STOPPING, NOTREADY, NOTREADY_STOPPED, NOTREADY_RUNNING,
                                    NOTREADY_NOTCREATED])
    STATUS_NOTREADY = (
        (NOTREADY, NOTREADY),
        (STOPPED, NOTREADY_STOPPED),
        (RUNNING, NOTREADY_RUNNING),
        (FROZEN, NOTREADY_FROZEN),
        (NOTCREATED, NOTREADY_NOTCREATED),
    )

    STATUS_TRANSITION_DICT = frozendict({  # PUT vm_status actions
        'start': RUNNING,
        'stop': STOPPED,
        'reboot': RUNNING,
    })

    DISK_BLOCK_SIZE = frozendict({
        _OSType.LINUX: 4096,
        _OSType.SUNOS: 131072,
        _OSType.BSD: 32768,
        _OSType.WINDOWS: 4096,
        _OSType.SUNOS_ZONE: 131072,
        _OSType.LINUX_ZONE: 131072,
    })

    RESERVED_MDATA_KEYS = frozenset(['resize_needed'])  # Bug #chili-721

    _DISKS_REMOVE_EMPTY = ()
    _NICS_REMOVE_EMPTY = (('gateway', ''), ('allowed_ips', ()), ('mtu', None))

    _pk_key = 'vm_uuid'  # _UserTasksModel
    _log_name_attr = 'hostname'  # _UserTasksModel
    _cache_status = True  # _StatusModel
    _update_changed = False  # _StatusModel
    _orig_node = None  # Original value of node if changed
    _node_changed = False  # Node has changed
    _tags = None  # New tags set in save()
    _first_disk_image = NOT_PROVIDED  # Cache first disk Image object
    _status_display = None  # Cached last known state
    new = False

    uuid = models.CharField(_('UUID'), max_length=36, primary_key=True, blank=False, null=False)
    hostname = models.CharField(_('Hostname'), max_length=255, unique=True)
    alias = models.CharField(_('User alias'), max_length=24)
    vnc_port = models.IntegerField(_('VNC port'))
    ostype = models.SmallIntegerField(_('Guest OS type'), choices=_OSType.OSTYPE)
    hvm_type = models.SmallIntegerField(_('Hypervisor type'), choices=_HVMType.HVM_TYPE)
    status = models.SmallIntegerField(_('Status'), choices=STATUS, default=NOTCREATED, db_index=True)
    owner = models.ForeignKey(User, verbose_name=_('Owner'), on_delete=models.PROTECT)
    node = models.ForeignKey(Node, null=True, blank=True, verbose_name=_('Node'))
    dc = models.ForeignKey(Dc, verbose_name=_('Datacenter'))
    template = models.ForeignKey(VmTemplate, blank=True, null=True, on_delete=models.SET_NULL,
                                 verbose_name=_('Template'))
    uptime = models.IntegerField(_('Aggregated uptime'), default=0, editable=False)
    uptime_changed = models.IntegerField(_('Last update of aggregated uptime'), default=0, editable=False)
    note = models.TextField(_('Note'), blank=True)

    # don't access 'encoded_data' directly, use the 'data' property instead, etc
    # default is an empty dict
    enc_json_active = models.TextField(blank=False, editable=False, default=_JsonPickleModel.EMPTY)
    enc_info = models.TextField(blank=False, editable=False, default=_JsonPickleModel.EMPTY)

    tags = TaggableManager(through=TagVm, blank=True)

    slave_vms = CommaSeparatedUUIDField(_('Slave servers'), blank=True, default='')

    class Meta:
        app_label = 'vms'
        verbose_name = _('VM')
        verbose_name_plural = _('Virtual machines')
        unique_together = (
            #  ('dc', 'owner', 'alias'),  # Not applicable for slave VMs
            ('node', 'vnc_port'),
        )

    # json_active is the current configuration of VM
    # It should change only after successful VM creation/update
    @property
    def json_active(self):
        return self._decode(self.enc_json_active)

    @json_active.setter
    def json_active(self, data):
        self.enc_json_active = self._encode(data)
        self._update_changed = True

    # info property is used to store vmadm info dict
    # It is updated after some status changes
    @property
    def info(self):
        return self._decode(self.enc_info)

    @info.setter
    def info(self, data):
        self.enc_info = self._encode(data)

    # FQDN tuple (hostname, domain) cache
    _fqdn = (None, None)
    _available_domains = None  # List of valid domains for hostname

    def __unicode__(self):
        return '%s' % self.hostname

    def __init__(self, *args, **kwargs):
        super(Vm, self).__init__(*args, **kwargs)
        if not self.uuid:
            self.uuid = str(uuid4())
            self.new = True
            self._update_changed = True

    @property
    def name(self):  # task log requirement
        return self.hostname

    @property
    def _interface_prefix(self):
        """Based on observation: behaviour is not documented by upstream."""
        if self.ostype == self.LINUX_ZONE:
            return 'eth'
        else:
            return 'net'

    def update_node_history(self, orig_node=None):
        """Store previous node into node_history"""
        _info = self.info

        if 'node_history' not in _info:
            _info['node_history'] = []

        if not orig_node:
            orig_node = self._orig_node

        if orig_node:
            _info['node_history'].append({
                'node_uuid': orig_node.uuid,
                'node_hostname': orig_node.hostname,
                'till': int(timezone.now().strftime('%s')),
            })

        self.info = _info

    @classmethod
    def generate_hostname(cls, dc, alias):
        """
        Generating new hostname from server alias.
        """
        alias = alias.strip().lower()
        suffix = ''
        i = 0
        # noinspection PyUnusedLocal
        hostname = alias

        while True:
            hostname = '%s%s.%s' % (alias, suffix, dc.domain)
            if not cls.objects.filter(hostname__iexact=hostname).exists():
                break
            i += 1
            suffix = '-' + str(i).zfill(2)

        return hostname

    def set_hvm_type(self, value):
        """Set HVM type"""
        self.hvm_type = int(value)
        brand = self.OSTYPE_BRAND.get(self.ostype, 'hvm')
        if brand is 'hvm':
            # 'kvm' here is default of the default:
            brand_default = self.HVM_TYPE_BRAND.get(settings.VMS_VM_HVM_TYPE_DEFAULT, 'kvm')
            # choose brand according to hvm_type (not needed for non-hvm as their brands are straightforward)
            brand = self.HVM_TYPE_BRAND.get(self.hvm_type, brand_default)
        self.save_item('brand', brand, save=False)

    def set_ostype(self, value):
        """Set ostype and brand"""
        self.ostype = int(value)
        brand = self.OSTYPE_BRAND.get(self.ostype, 'hvm')
        if brand is not 'hvm':
            # update brand according to ostype
            self.save_item('brand', brand, save=False)

    def set_tags(self, tags):
        """Store tags for save()"""
        self._tags = tags

    def set_node(self, node):
        """Set new VM node"""
        if self.node != node:
            if self._orig_node:
                raise SuspiciousOperation('Cannot change node multiple times without saving!')
            self._orig_node = self.node
            self._node_changed = True
            self.node = node

    def choose_node(self):
        """Call Node method to choose the right node for a new VM"""
        self.set_node(Node.choose(self))
        return self.node

    def set_notready(self, save=True):
        """Set status to notready according to current status"""
        self.status = dict(self.STATUS_NOTREADY).get(self.status, self.NOTREADY)
        if save:
            self.save_status()

    def revert_notready(self, save=True):
        """Revert notready to previous status"""
        self.status = dict([(b, a) for a, b in self.STATUS_NOTREADY]).get(self.status, self.status)
        if save:
            self.save_status()

    def choose_vnc_port(self):
        """Call to choose new unique VNC port for a new VM.
        Call after valid node is set and call save() afterwards."""
        try:
            last = Vm.objects.filter(node=self.node).exclude(uuid=self.uuid).order_by('-vnc_port')[0:1].get()
            new_port = last.vnc_port + 1
            if new_port >= 65535:
                new_port = 15901
            # noinspection PyCompatibility
            for port in xrange(new_port, 65536):
                try:
                    Vm.objects.get(node=self.node, vnc_port=new_port)
                except Vm.DoesNotExist:
                    self.vnc_port = port
                    break
            else:
                raise RuntimeError('Could not find free VNC port')
        except Vm.DoesNotExist:
            self.vnc_port = 15901

        return self.vnc_port

    @staticmethod
    def available_domains(dc, user):
        """Return set of available domains"""
        if not dc.settings.DNS_ENABLED:
            return set()

        from pdns.models import Domain  # circular imports
        # Only domains available in this DC can be used
        dc_domain_ids = list(dc.domaindc_set.values_list('domain_id', flat=True))
        # Also exclude some unusable server domains here
        domain_filter = Q(id__in=dc_domain_ids) & ~Domain.QServerExclude

        if not user.is_admin(dc=dc):  # Normal users should not be allowed to see private domains they don't own
            domain_filter = domain_filter & (Q(access=Domain.PUBLIC) | Q(access=Domain.PRIVATE, user=user.id))

        domains = set(Domain.objects.filter(domain_filter).values_list('name', flat=True))
        domains.add(dc.domain)  # The default DC domain is always available (even if it is private)

        return domains

    # noinspection PyShadowingNames
    def hostname_is_valid_fqdn(self, cache=True):
        """Split the FQDN into hostname and domain parts. Also check if the
        domain name is valid."""
        if cache and self.fqdn_hostname:
            return bool(self.fqdn_domain)

        # Valid domains are DC domains
        if self._available_domains is None:
            # noinspection PyTypeChecker
            self._available_domains = self.available_domains(self.dc, self.owner)

        if self.dc.settings.DNS_ENABLED:
            fqdn = self.hostname.split('.')
            # Find domain and check if the domain is legit
            for i in range(1, len(fqdn)):
                _domain = '.'.join(fqdn[i:])
                if _domain in self._available_domains:
                    _hostname = '.'.join(fqdn[:i])
                    # Cache valid FQDN tuple
                    self._fqdn = (_hostname, _domain)
                    return True

        # FQDN is invalid
        self._fqdn = (self.hostname, None)
        return False

    @property  # Cached hostname part of _fqdn tuple, created after fqdn_is_valid
    def fqdn_hostname(self):
        return self._fqdn[0]

    @property  # Cached domain part of _fqdn tuple, created after fqdn_is_valid
    def fqdn_domain(self):
        return self._fqdn[1]

    def update_hostname(self, new_hostname=None):
        """Delete old DNS records for the old hostname and create new DNS A
        Records for the new hostname. New records are created only if the
        new hostname is valid."""
        from pdns.models import Record  # Circular import

        # Check if cached fqdn exists (=> if hostname_is_valid_fqdn was called)
        assert (self._fqdn != (None, None)), 'fqdn not cached'

        valid = False

        if not self.dc.settings.DNS_ENABLED:
            return valid

        # Got new hostname (=> not called from save())
        if new_hostname:
            # Generate self._fqdn pair for the old hostname
            self.hostname_is_valid_fqdn(cache=False)
            # Set the new hostname
            self.hostname = new_hostname

        # Old hostname should be cached in self._fqdn
        if self.fqdn_hostname and self.fqdn_domain:
            old_hostname = self.fqdn_hostname + '.' + self.fqdn_domain
            old_domain = self.fqdn_domain
            # Validate and create new self._fqdn pair
            valid = self.hostname_is_valid_fqdn(cache=False)

            for dns in Record.get_records_A(old_hostname, old_domain):
                ipaddr = dns.content
                dns.delete()
                if valid:
                    Record.add_record(Record.A, self.fqdn_domain, self.hostname, ipaddr)

        return valid

    def sync_template(self):
        """Copy data from template to VM. Returns template json."""
        # copy ostype setting from template
        if self.template.ostype is not None:
            self.ostype = self.template.ostype

        # copy json data from template
        return self.template.get_json()

    def sync_json(self, sync_template=False, sync_defaults=False):
        """Sync json to outside attributes and set defaults.
        This should be called when creating new VM.
        Also copy data from template if needed."""
        _json = self.json
        dc_settings = self.dc.settings

        # new VM -> set the defaults
        if sync_defaults and 'uuid' not in _json:
            _json.update2(dc_settings.VMS_VM_JSON_DEFAULTS.copy())
            _json['resolvers'] = dc_settings.VMS_VM_RESOLVERS_DEFAULT

        # check if we have specified a template
        if sync_template and self.template is not None:
            _json.update2(self.sync_template())

        # must have
        _json['uuid'] = self.uuid
        _json['hostname'] = self.hostname  # fqdn
        _json['owner_uuid'] = str(self.owner.id)
        _json['alias'] = self.hostname
        # _json['internal_metadata_namespaces'] = ['es']
        _json['internal_metadata']['alias'] = self.alias
        _json['internal_metadata']['ostype'] = self.ostype

        if not self.template:  # The name is saved in sync_template (part of template json)
            _json['internal_metadata'].pop('template', None)

        # just in case; the new VM would miss these
        if 'server_uuid' in _json and self.node is not None:
            _json['server_uuid'] = self.node.uuid
        if 'autoboot' not in _json:
            _json['autoboot'] = False
        if 'brand' not in _json:
            _json['brand'] = 'kvm'
        if 'customer_metadata' not in _json:
            _json['customer_metadata'] = {}

        # remove internal_metadata keys with problematic values
        for k, v in _json['internal_metadata'].items():
            if isinstance(v, (list, tuple, dict, NoneType)):
                del _json['internal_metadata'][k]

        if _json['brand'] == 'kvm':
            # add qemu agent options
            _json['qemu_extra_opts'] = settings.VMS_VM_QEMU_EXTRA_OPTS

            # save vnc port
            if self.node is not None:
                _json['vnc_port'] = self.vnc_port
            else:
                _json.pop('vnc_port', None)
        else:
            if settings.VMS_ZONE_FEATURE_LEVEL >= 2:
                # Issue #chili-867 - these limits won't affect creating snapshots and datasets from global zone
                _json['zfs_filesystem_limit'] = _json['zfs_snapshot_limit'] = 0

            if self.ostype == self.LINUX_ZONE and 'kernel_version' not in _json:
                _json['kernel_version'] = dc_settings.VMS_VM_LX_KERNEL_VERSION_DEFAULT

        self.json = _json

    # noinspection PyMethodMayBeStatic
    def _set_cloud_init(self, json, attr, value):
        """Create or append data into customer_metadata.cloud-init:attr. Value is always a list or tuple"""
        # noinspection PyAugmentAssignment
        attr = 'cloud-init:' + attr

        if attr in json['customer_metadata']:
            return False
        else:
            user_data = ['#cloud-config']
            user_data.extend(value)
            json['customer_metadata'][attr] = '\n'.join(user_data)
            return True

    def set_root_pw(self):
        """Generate json['internal_metadata']['root_pw']"""
        _json = self.json

        try:
            passwd = _json['internal_metadata']['root_pw']
        except KeyError:
            passwd = User.objects.make_random_password(length=10)
            _json['internal_metadata']['root_pw'] = passwd

        self._set_cloud_init(_json, 'user-data', ['chpasswd:', ' expire: false', ' list: |', '   root:%s' % passwd])
        self.json = _json

    def fix_json(self, deploy=False, resize=False, recreate=False):  # noqa: R701
        """So just before any vmadm create command we have to clean some stuff from the json.
        Currently we remove:
            - disks.*.path if media is 'disk'
            - disks.*.size if image_uuid is specified
            - disks.*.block_size if image_uuid is specified
            - disks.*.refreservation is removed if brand==bhyve (it is then set to 'auto')

        Other changes:
            - autoboot is set to false
            - list of attributes that create "invalid property" warnings

        When deploy is needed we will return a json with customer_metadata:
            - resize_needed
            - root_pw (moved to internal_metadata)
            - root_authorized_keys"""
        _json = self.json
        _json['autoboot'] = False

        for prop in ('snapshots', 'create_timestamp', 'server_uuid', 'state', 'zonepath', 'zone_state', 'zoneid',
                     'zfs_filesystem', 'last_modified', 'v', 'platform_buildstamp', 'limit_priv', 'nowait', 'pid',
                     'filesystems', 'headnode_id', 'datacenter_name', 'zonename', 'exit_status', 'exit_timestamp'):
            try:
                del _json[prop]
            except KeyError:
                pass

        if self.is_hvm():
            for x in ('routes', 'dns_domain'):
                try:
                    del _json[x]
                except KeyError:
                    pass

            if 'disks' in _json:
                for i, disk in enumerate(list(_json['disks'])):  # list() for creating a copy
                    try:
                        if disk.get('media', 'disk') == 'disk':
                            del _json['disks'][i]['path']
                    except KeyError:
                        pass
                    try:
                        if 'image_uuid' in disk:
                            size = _json['disks'][i].pop('size')
                            try:
                                if resize and size != _json['disks'][i]['image_size']:
                                    _json['customer_metadata']['resize_needed'] = 'yes'
                                    if 'refreservation' in disk:
                                        _json['disks'][i].pop('refreservation')
                            except KeyError:
                                pass
                    except KeyError:
                        pass
                    try:
                        if 'image_uuid' in disk:
                            del _json['disks'][i]['block_size']
                    except KeyError:
                        pass
                    try:
                        del _json['disks'][i]['zfs_filesystem']
                    except KeyError:
                        pass
                    try:
                        if self.is_bhyve():
                            del _json['disks'][i]['refreservation']
                    except KeyError:
                        pass

        else:  # zone
            if _json.pop('datasets', None):
                _json['delegate_dataset'] = True

        # root_pw should be generated with self.set_root_pw and saved afterwards
        # just set root_authorized_keys
        if 'root_authorized_keys' not in _json['customer_metadata'] or recreate:
            keys = set(self.dc.settings.VMS_VM_SSH_KEYS_DEFAULT)

            if self.owner:
                keys.update(self.owner.usersshkey_set.all().values_list('key', flat=True))

            if keys:
                _json['customer_metadata']['root_authorized_keys'] = '\n'.join(keys)

        if not self.is_hvm() and 'user-script' not in _json['customer_metadata']:  # Bug #chili-406
            user_script = settings.VMS_VM_ZONE_USER_SCRIPT_DEFAULT

            if deploy:
                deploy_cmd = '/usr/sbin/poweroff'
            else:
                deploy_cmd = 'echo'

            user_script = user_script.format(image_deploy=deploy_cmd)
            _json['customer_metadata']['user-script'] = user_script

        return _json

    def is_notcreated(self):
        """Return True if VM is not created on compute node"""
        return self.status == self.NOTCREATED

    def is_deployed(self):
        """Return True if VM is or is being created on compute node"""
        return self.status != self.NOTCREATED

    def is_blank(self):
        """Check if a image for the first disk was specified. If no, then we
        have a custom/blank VM."""
        try:
            first_disk = self.json_get_disks()[0]
        except IndexError:
            return True
        else:
            if 'image_uuid' in first_disk:
                return False
        return True

    def is_installed(self):
        """Check if a blank VM has been installed. If the VM is created from
        image then this will always return True."""
        if not self.is_blank():
            return True
        if self.is_hvm():
            return self.installed
        return True

    def is_deploy_needed(self):
        """Check if a image for the first disk was specified. If yes and the
        image needs deployment, then we need to deploy the VM."""
        first_disk = self.json_get_first_disk_image()
        try:
            return first_disk and first_disk.deploy
        except AttributeError:  # Not an image at all
            return False

    def is_resize_needed(self):
        """Check if a image for the first disk was specified. If yes and the
        image is resizable, then we need to resize the VM."""
        first_disk = self.json_get_first_disk_image()
        try:
            return first_disk and first_disk.resize
        except AttributeError:  # Not an image at all
            return False

    def is_hvm(self):
        """Check hypervisor type and return True for KVM or BHYVE"""
        return self.hvm_type in self.HVM

    def is_kvm(self):
        """Check hypervisor type and return True for KVM"""
        return self.hvm_type is _HVMType.Hypervisor_KVM

    def is_bhyve(self):
        """Check hypervisor type and return True for BHYVE"""
        return self.hvm_type is _HVMType.Hypervisor_BHYVE

    def is_bootable(self):
        """Check if HVM has boot flag or OS zone has an image - bug #chili-418"""
        if self.is_hvm():
            diskboot = [d.get('boot', False) for d in self.json_get_disks()]
            if not diskboot:  # VM without disks is OK
                return True
            return any(diskboot)
        else:
            return not self.is_blank()

    # noinspection PyUnusedLocal
    @staticmethod
    def post_delete(sender, instance, **kwargs):
        """Remove cache items and cleanup node and storage resources"""
        if instance.node:
            instance.node.update_resources(save=True)
            zpools = instance.get_disks().keys()
            dc = instance.dc
            if zpools:
                for ns in instance.node.get_node_storages(dc, zpools=zpools):
                    ns.update_resources(save=True, recalculate_dc_vms_size=(dc,), recalculate_dc_snapshots_size=(dc,))

    def save(self, sync_json=False, update_hostname=False, update_node_resources=False,
             update_storage_resources=(), keep_vnc_port=False, **kwargs):
        """You can update the hostname, update node resource and set the json
        defaults before saving the object"""
        # Update node_history and vnc port if node changed
        if self._node_changed:
            self.update_node_history()

            if not keep_vnc_port:
                self.vnc_port = None

        # VNC port is NULL at the beginning
        if self.vnc_port is None:
            self.choose_vnc_port()

        # Update json
        if sync_json or self._node_changed:
            self.sync_json()

        # Classic django model.save()
        ret = super(Vm, self).save(**kwargs)
        self._update_changed = False

        # Save tags if set
        if self._tags is not None:
            # noinspection PyArgumentList
            self.tags.set(*self._tags)
            self._tags = None

        # update node storage resources
        if update_storage_resources is True:
            update_storage_resources = self.get_node_storages()

        for ns in update_storage_resources:
            ns.update_resources(save=True, recalculate_dc_vms_size=(self.dc,), recalculate_dc_snapshots_size=(self.dc,))

        # Update node resources on old and new node
        if self._node_changed:
            if self.node:
                self.node.update_resources(save=True)
            if self._orig_node:
                self._orig_node.update_resources(save=True)
            # Back to defaults
            self._node_changed = False
            self._orig_node = None
        elif update_node_resources and self.node:
            self.node.update_resources(save=True)

        # Update DNS records and cached fqdn if needed
        # Cached fqdn attributes must exist before this operation
        # (=> someone has to call vm.hostname_is_valid_fqdn())
        if update_hostname:
            self.update_hostname()

        return ret

    def save_disks(self, disks, **kwargs):
        """Set disks list in json"""
        if self.is_hvm():
            for i, disk in enumerate(disks):
                # Remove nocreate attribute if empty
                if 'nocreate' in disk and not disk['nocreate']:
                    del disks[i]['nocreate']
                # Remove if empty
                for e in self._DISKS_REMOVE_EMPTY:
                    if e in disk and not disk[e]:
                        del disk[i][e]

            return self.save_item('disks', disks, **kwargs)

        # Solaris zone
        try:
            root = disks[0]
        except IndexError:
            return

        _json = self.json
        # root dataset
        _json['quota'] = int(round(float(root['size']) / float(1024)))
        _json['zfs_root_compression'] = root['compression']
        _json['zfs_root_recsize'] = root['block_size']
        _json['zpool'] = root['zpool']
        if root.get('image_uuid', self.dc.settings.VMS_DISK_IMAGE_ZONE_DEFAULT):
            _json['image_uuid'] = root['image_uuid']
        else:
            _json.pop('image_uuid', None)

        # data dataset
        try:
            data = disks[1]
        except IndexError:
            if self.is_notcreated():
                _json.pop('delegate_dataset', None)
                _json.pop('zfs_data_compression', None)
                _json.pop('zfs_data_recsize', None)
        else:
            if self.is_notcreated():
                _json['delegate_dataset'] = True
            _json['zfs_data_compression'] = data['compression']
            _json['zfs_data_recsize'] = data['block_size']

        self.json = _json

        return self.save(**kwargs)

    def save_nics(self, nics, monitoring_ip=None, **kwargs):
        """Set nics list in json"""
        hvm = self.is_hvm()

        for i, nic in enumerate(nics):
            # Bug #chili-239
            nics[i]['interface'] = self._interface_prefix + str(i)
            # Remove MAC attribute if empty
            if 'mac' in nic and not nic['mac']:
                del nics[i]['mac']
            # Remove primary attribute if False
            if 'primary' in nic and not nic['primary']:
                del nics[i]['primary']
            # Remove ips key from nic dictionary before saving changes
            if 'ips' in nic:
                del nics[i]['ips']
            # Remove gateways key from nic dictionary before saving changes
            if 'gateways' in nic:
                del nics[i]['gateways']
            # Remove model if OS zone
            if not hvm and 'model' in nic:
                del nics[i]['model']
            # Remove if empty
            for e, __ in self._NICS_REMOVE_EMPTY:
                if e in nic and not nic[e]:
                    del nics[i][e]

        if monitoring_ip is not None:
            self.monitoring_ip = monitoring_ip  # will be saved in save_item()

        return self.save_item('nics', nics, **kwargs)

    def save_metadata(self, key, value, metadata='internal_metadata', save=True, **kwargs):
        """Set item in metadata object - by default internal_metadata"""
        return self.save_item(key, value, save=save, metadata=metadata, **kwargs)

    def delete_metadata(self, key, metadata='internal_metadata', save=True, **kwargs):
        """Set item in metadata object - by default internal_metadata"""
        return self.delete_item(key, save=save, metadata=metadata, **kwargs)

    @property
    def internal_metadata(self):
        """Return json['internal_metadata'] dict"""
        return self.json.get('internal_metadata', {})

    @property
    def customer_metadata(self):
        """Return json['customer_metadata'] dict"""
        return self.json.get('customer_metadata', {})

    @customer_metadata.setter
    def customer_metadata(self, value):
        """Update json['customer_metadata'] dict"""
        assert isinstance(value, dict)
        _json = self.json
        _json['customer_metadata'] = value
        self.json = _json

    def save_info(self, key, value, save=True, **kwargs):
        """Update or set info attribute"""
        _info = self.info
        _info[key] = value
        self.info = _info

        if save:
            return self.save(**kwargs)
        else:
            return True

    def update_json(self, new_json):
        """Recursively update json with new dict"""
        _json = self.json
        _json.update2(new_json)
        self.json = _json

    def create_json_update_nested(self, item, key, remove_empty=()):
        """Return add_, remove_ and update_ lists for specific item (disks or nics).
        See special notes on update command in man vmadm.
        """
        res = SortedPickleDict()

        j = pair_keys_to_items(self.json.get(item, []), key)
        j_active = pair_keys_to_items(self.json_active.get(item, []), key)

        add_, remove_, update_ = diff_dict_nested(j_active, j, key, remove_empty=remove_empty)

        if remove_:
            res['remove_' + item] = remove_
        if add_:
            res['add_' + item] = add_
        if update_:
            res['update_' + item] = update_

        return res

    def create_json_update_disks(self):
        """Call create_json_update_nested() for json['disks']"""
        if self.is_hvm():
            return self.create_json_update_nested('disks', 'path', remove_empty=self._DISKS_REMOVE_EMPTY)
        return {}  # OS zones have all disks properties in json root

    def create_json_update_nics(self):
        """Call create_json_update_nested() for json['nics']"""
        return self.create_json_update_nested('nics', 'mac', remove_empty=self._NICS_REMOVE_EMPTY)

    def create_json_update(self):
        """Return a modified version of json attribute used for VM update.
        The resulting dict is missing the disks and nics keys and some other
        properties which cannot be updated.
        """
        noupdate = ('uuid', 'brand', 'create_timestamp', 'customer_metadata', 'datasets', 'delegate_dataset', 'disks',
                    'filesystems', 'image_uuid', 'internal_metadata', 'last_modified', 'limit_priv', 'nics',
                    'mdata_exec_timeout', 'nowait', 'pid', 'routes', 'server_uuid', 'state', 'tags', 'type',
                    'zfs_filesystem', 'zfs_root_recsize', 'zone_state', 'zoneid', 'zonename', 'zonepath', 'zpool',
                    'datacenter_name', 'headnode_id', 'dns_domain', 'exit_status', 'exit_timestamp')

        noexist_false = ('do_not_inventory',)
        json = self.json
        json_active = self.json_active
        res = SortedPickleDict(json)

        # Remove items which cannot be updated
        for i in noupdate:
            try:
                del res[i]
            except KeyError:
                pass

        # Set changed items which do not exist if set to false
        for i in noexist_false:
            if i not in res and i in json_active:
                res[i] = False

        # Remove unchanged items
        for i in res.keys():
            if i in json_active and res[i] == json_active[i]:
                del res[i]

        # Simple objects are changed with set_/remove_ attributes
        for item in ('internal_metadata', 'customer_metadata', 'routes', 'tags'):
            if item in json_active or item in json:
                set_, remove_ = diff_dict(json_active.get(item, {}), json.get(item, {}))
                if remove_:
                    res['remove_' + item] = remove_
                if set_:
                    res['set_' + item] = set_

        return res

    def json_update(self):
        """Create vmadm update compatible json"""
        _json = self.create_json_update()
        _json.update(self.create_json_update_nics())

        if self.is_hvm():
            _json.update(self.create_json_update_disks())

        return _json

    @staticmethod
    def parse_json_disks(uuid, json, is_hvm, is_notcreated=False, zpool=None):
        """Return list of nice disks."""
        if is_hvm:
            disks = [d for d in json.get('disks', []) if is_disk(d, zpool)]
        else:
            _zpool = json.get('zpool', Node.ZPOOL)

            if zpool and _zpool != zpool:
                return []

            root = _zpool + '/' + uuid
            quota = json.get('quota', 0) * 1024
            disks = [{
                'path': 'disk0',
                'zfs_filesystem': json.get('zfs_filesystem', root),
                'size': quota,
                'refreservation': 0,
                'boot': True,
                'model': 'zfs',
                'compression': json.get('zfs_root_compression', 'off'),
                'block_size': json.get('zfs_root_recsize', 131072),
                'zpool': _zpool,
            }]
            img = json.get('image_uuid', None)
            if img:
                disks[0]['image_uuid'] = img

            data = root + '/data'
            if (is_notcreated and json.get('delegate_dataset', False)) or data in json.get('datasets', []):
                disks.append({
                    'path': 'disk1',
                    'zfs_filesystem': data,
                    'size': quota,
                    'refreservation': 0,
                    'boot': False,
                    'model': 'zfs',
                    'compression': json.get('zfs_data_compression', 'off'),
                    'block_size': json.get('zfs_data_recsize', 131072),
                    'zpool': _zpool,
                })

        return disks

    def _get_disks(self, json, zpool=None):
        """Return list of nice disks."""
        return self.parse_json_disks(self.uuid, json, self.is_hvm(), is_notcreated=self.is_notcreated(), zpool=zpool)

    def json_get_disks(self):
        """Get disks from json."""
        return self._get_disks(self.json)

    def json_active_get_disks(self):
        """Get disks from json_active."""
        return self._get_disks(self.json_active)

    @staticmethod
    def get_real_disk_id(disk):
        """Return real disk ID (disk number in disks.*.path) from disk object (dict)"""
        return int(disk['path'].split('-')[-1].lstrip('disk'))

    @classmethod
    def get_disk_map(cls, json):
        """Return dict with disk path ID as key and disk ID as value from active json."""
        ret = {}

        for i, disk in enumerate(json):
            ret[cls.get_real_disk_id(disk)] = i

        return ret

    def json_active_get_disks_map(self):
        """Return disk map from active json"""
        return self.get_disk_map(self.json_active_get_disks())

    def json_get_first_disk_image(self):
        """Get VM first disk Image object"""
        try:
            first_disk = self.json_get_disks()[0]
        except IndexError:
            return None
        else:
            from vms.models.image import Image

            if 'image_uuid' in first_disk:
                return Image.objects.get(uuid=first_disk['image_uuid'])
            else:
                return Image.CUSTOM.get(self.ostype, None)

    def json_get_cached_first_disk_image(self):
        if self._first_disk_image is NOT_PROVIDED:
            self._first_disk_image = self.json_get_first_disk_image()
        return self._first_disk_image

    @property
    def disk_image(self):
        """Return image name of the first disk - used by monitoring"""
        return getattr(self.json_get_cached_first_disk_image(), 'name', '')

    @property
    def disk_image_abbr(self):
        """Return image abbreviation of the first disk - used by monitoring"""
        return self.disk_image.split('-')[0]

    @staticmethod
    def get_nics(json):
        """Return list of nice nics."""
        nics = json.get('nics', [])
        return nics

    def json_get_nics(self):
        """Get nics from json."""
        return self.get_nics(self.json)

    def json_active_get_nics(self):
        """Get nics from json_active."""
        return self.get_nics(self.json_active)

    @staticmethod
    def _get_ips(nics, primary_ips=True, allowed_ips=True):
        """Return list of VM IPs from json.nics list"""
        ips = []

        for nic in nics:
            if primary_ips and is_ip(nic):
                ips.append(nic['ip'])
            if allowed_ips:
                ips.extend(nic.get('allowed_ips', []))

        return ips

    def json_get_ips(self, **kwargs):
        """Get IPs on all nics from json."""
        return self._get_ips(self.json_get_nics(), **kwargs)

    def json_active_get_ips(self, **kwargs):
        """Get IPs on nics from json_active."""
        return self._get_ips(self.json_active_get_nics(), **kwargs)

    @staticmethod
    def get_real_nic_id(nic):
        """Return real network ID (net number in nics.*.interface) from nic object (dict)"""
        return int(nic['interface'].lstrip('net').lstrip('eth'))

    @classmethod
    def get_nics_map(cls, json):
        """Return dict with nic interface ID as key and nic ID as value from active json."""
        ret = {}

        for i, nic in enumerate(json):
            ret[cls.get_real_nic_id(nic)] = i

        return ret

    def json_active_get_nics_map(self):
        """Return nics map from json_active."""
        return self.get_nics_map(self.json_active_get_nics())

    def get_cpu_ram(self, ram_overhead=False, ignore_cpu_ram=None):
        """Return tuple (vCPUS, RAM) used in resource accounting. Function may return zeros when the VM is a slave VM
        without reserved resources; if you want the CPU, RAM count for these kind of VMs, use `ignore_cpu_ram=False`"""
        json = self.json
        json_active = self.json_active

        if ignore_cpu_ram is not False and self.is_slave_vm() and not self.slavevm.reserve_resources:
            return 0, 0

        # The CPU count is calculated from cpu_cap of the zone
        cpu = self._get_cpu_zone(json)
        cpu_active = self._get_cpu_zone(json_active)

        if self.is_hvm():
            if ram_overhead:
                ram = json.get('max_physical_memory', 0)
                ram_active = json_active.get('max_physical_memory', 0)
            else:
                ram = json.get('ram', 0)
                ram_active = json_active.get('ram', 0)
        else:
            ram = json.get('max_physical_memory', 0)
            ram_active = json_active.get('max_physical_memory', 0)

        if self.is_deployed():
            if cpu_active > cpu:
                cpu = cpu_active

            if ram_active > ram:
                ram = ram_active

        return cpu, ram

    def get_disks(self, zpool=None, active=False):
        """Return dict {disk_pool_x: sum(disk_size_on_pool_x), disk_pool_y: sum(disk_size_on_pool_y)}"""
        dsk = defaultdict(int)

        if active:
            json = self.json_active
        else:
            json = self.json

        if self.is_hvm():
            for i in self._get_disks(json, zpool=zpool):
                dsk[i['zpool']] += i['size']
        else:
            try:  # Count only root dataset quota
                root = self._get_disks(json, zpool=zpool)[0]
            except IndexError:
                pass
            else:
                dsk[root['zpool']] = root['size']

        return dsk

    def get_used_disk_pools(self):
        """Return set of used disk pools"""
        json = self.json
        json_active = self.json_active
        root_zpool = json.get('zpool', Node.ZPOOL)  # For KVM and ZONE
        zpools = {root_zpool, json_active.get('zpool', root_zpool)}

        if self.is_hvm():
            for _json in (json, json_active):
                for _disk in self._get_disks(_json):
                    zpools.add(_disk['zpool'])

        return zpools

    def get_disk_size(self, zpool=None):
        """Return cumulative disk size for a pool used in DC resource accounting"""
        dsk_size = sum(self.get_disks(zpool=zpool).values())

        if self.is_deployed():
            dsk_size_active = sum(self.get_disks(zpool=zpool, active=True).values())

            if dsk_size_active > dsk_size:
                return dsk_size_active

        return dsk_size

    def get_cpu_ram_disk(self, zpool=None, ram_overhead=False, ignore_cpu_ram=None, ignore_disk=None):
        """Return tuple (vCPUS, RAM, sum(disk_size_on_zpool)) used in resource accounting.
        With `ignore_disk=True` or `ignore_cpu_ram=True` the returned corresponding values will be zero.
        The default `ignore_cpu_ram=None` may return zero values for the vCPUS and RAM fields if the VM is a slave VM;
        this behaviour can be disabled even for a slave VM with `ignore_cpu_ram` set to `False`.
        """
        if ignore_cpu_ram:
            cpu, ram = 0, 0
        else:
            cpu, ram = self.get_cpu_ram(ram_overhead=ram_overhead, ignore_cpu_ram=ignore_cpu_ram)

        if ignore_disk:
            dsk = 0
        else:
            dsk = self.get_disk_size(zpool=zpool)

        return cpu, ram, dsk

    def get_node_storages(self):
        """Return queryset/list of NodeStorages for this VM"""
        if self.node:
            zpools = self.get_disks().keys()
            if zpools:
                return self.node.get_node_storages(self.dc, zpools=zpools)
        return []

    def get_node_storages_disk_map(self):
        """Return {disk_id: NodeStorage} mapping for all disks of this VM"""
        if self.node:
            get_node_storage = self.node.get_node_storage
            return {self.get_real_disk_id(disk): get_node_storage(self.dc, disk['zpool'])
                    for disk in self.json_get_disks()}
        else:
            return {}

    def get_node_storage(self, real_disk_id):
        """Fetch zpool/NodeStorage object according to real_disk_id"""
        return self.get_node_storages_disk_map()[real_disk_id]

    def default_apiview(self):
        """Return dict with attributes which are always available in apiview"""
        return {
            'hostname': self.hostname,
            'status': self.status,
            'status_display': self.status_display(),
            'define_changed': self.json_changed(),
            'locked': self.locked,
        }

    def get_status_changing_tasks(self):
        """Return appropriate task if VM status is changing"""
        return self.get_tasks(match_dict={'view': 'vm_status', 'method': 'PUT'})

    def is_changing_status(self):
        """Return True if VM status is changing"""
        return bool(self.get_status_changing_tasks())

    def get_target_status(self, vm_status_tasks=None):
        """Return VM status the VM is transitioning to (only if a vm_status task is running)"""
        if vm_status_tasks is None:
            vm_status_tasks = self.get_status_changing_tasks()

        actions = set(task.get('action') for _, task in iteritems(vm_status_tasks))

        if actions:
            if len(actions) == 1:
                return self.STATUS_TRANSITION_DICT.get(actions.pop(), self.UNKNOWN)
            else:
                return self.UNKNOWN  # Two or more different vm_status actions

        return None  # Not changing status

    def is_deploying(self):
        """Return True if VM has deploying status"""
        return self.status in (self.CREATING, self.DEPLOYING_DUMMY, self.DEPLOYING_START, self.DEPLOYING_FINISH)

    @property  # key is checked in api to determine deploy status
    def _deploy_finished_key(self):
        return settings.CACHE_KEY_PREFIX + ':' + self.pk + ':deploy_finished'

    def set_deploy_finished(self):
        """Create specific key in cache, which is checked by the api to determine deployment state"""
        redis.set(self._deploy_finished_key, 1)

    def has_deploy_finished(self):
        """Check if specific key exists to determine deployment state"""
        if redis.exists(self._deploy_finished_key):
            redis.delete(self._deploy_finished_key)
            return True
        return False

    @property  # just a helper, so we have one method to construct the cache key
    def _screenshot_key(self):
        return settings.CACHE_KEY_PREFIX + ':' + self.pk + ':screenshot'

    @property  # get base64 PNG screenshot from cache
    def screenshot(self):
        return redis.get(self._screenshot_key)

    @screenshot.setter  # set base64 PNG screenshot into cache
    def screenshot(self, image):
        redis.set(self._screenshot_key, image)

    # like get_status_display()
    def status_display(self, pending=True, unknown=True):
        """
        Return get_status_display() or pending if a vm_status task is running.
        If the status is stopping then return stopping, unless a vm_status
        force task is running. A bit complicated, but it makes sense :)
        """
        if unknown and self.node and self.node.status not in Node.STATUS_OPERATIONAL:
            return self.STATUS_UNKNOWN
        if not pending:
            return self.get_status_display()

        vm_status_tasks = self.get_status_changing_tasks()

        # Although a vm_status task is still running the VM may have already changed its status
        if vm_status_tasks and self.get_target_status(vm_status_tasks) != self.status:
            if self.status == self.STOPPING:
                if any(task.get('force', False) for _, task in iteritems(vm_status_tasks)):
                    self._status_display = self.STATUS_PENDING
                else:
                    self._status_display = self.get_status_display()
            else:
                self._status_display = self.STATUS_PENDING
        else:
            self._status_display = self.get_status_display()

        return self._status_display

    @property
    def state(self):
        """Display last known state"""
        if self._status_display is None:
            return self.status_display(unknown=False)
        else:
            return self._status_display

    def update_uptime(self, state=None, force_init=False):
        """
        Update VM uptime according to state when VM is stopped or started.
        """
        msg = None
        now = int(timezone.now().strftime('%s'))
        if not state:
            state = self.status

        if state == self.RUNNING or force_init:
            # VM is running for the first time
            if self.uptime_changed == 0 or self.uptime == 0:
                self.uptime += 1
                self.uptime_changed = now
                msg = 'VM %s started for the first time - initializing uptime' % (self.uuid,)

        # calculate and update VM uptime if stopped or frozen
        elif state == self.STOPPED or state == self.FROZEN:
            # this can be done only for already calculated uptime
            if self.uptime_changed != 0 and self.uptime != 0:
                self.uptime += now - self.uptime_changed
                self.uptime_changed = now
                msg = 'VM %s stopped - updating uptime' % (self.uuid,)

        return msg

    def node_history(self, since=0, till=None):
        """
        Query info['node_history'] list and return a list of dicts. Optional
        "since" and "till" parameters should be expressed in unix time (UTC)
        integers.
        """
        ret = []
        last_node_is_current = True

        # Current node
        current = {'node_uuid': None, 'node_hostname': None, 'till': till or int(timezone.now().strftime('%s'))}
        if self.node:
            current['node_uuid'] = self.node.uuid
            current['node_hostname'] = self.node.hostname

        # Get node history for wanted time period from self.info json
        if 'node_history' in self.info and self.info['node_history']:
            nh = self.info['node_history']

            for i in nh:
                if till and i['till'] >= till:
                    ret.append(i)
                    last_node_is_current = False
                    break

                if i['till'] > since:
                    ret.append(i)

        # Append current node if needed
        if last_node_is_current:
            ret.append(current)

        # Determine start of timeperiod. It's better be "since", because
        # self.created is not really the start we want
        begin = int(self.created.strftime('%s'))
        if since and since > begin:
            begin = since

        # Total length of measured time period
        total = ret[-1]['till'] - begin

        # Calculate time frame duration and weight
        for i in ret:
            i['since'] = begin
            i['duration'] = i['till'] - begin
            i['weight'] = round(float(i['duration']) / float(total), 8)
            begin = i['till']

        return ret

    def json_changed(self):
        """Has VM json changed?"""
        return self.json != self.json_active

    def json_disks_changed(self):
        """Has VM json.disks changed?"""
        return self.json_get_disks() != self.json_active_get_disks()

    def json_nics_changed(self):
        """Has VM json.nics changed?"""
        return self.json_get_nics() != self.json_active_get_nics()

    @property
    def uptime_actual(self):
        uptime = self.uptime

        if self.status == self.RUNNING and self.uptime_changed:
            uptime += int(timezone.now().strftime('%s')) - self.uptime_changed

        return uptime

    @property
    def ostype_text(self):  # Used by monitoring
        return self.get_ostype_display().lower().replace(' ', '_')

    @property
    def dc_name(self):  # Used by monitoring
        return self.dc.name

    @property  # Return host name used as Zabbix alias
    def zabbix_name(self):
        return '_' + self.hostname

    @property
    def zabbix_id(self):
        return self.uuid

    @property
    def external_zabbix_name(self):
        return self.hostname

    @property
    def external_zabbix_id(self):
        return '_' + self.uuid

    @property
    def zabbix_info(self):  # Return zabbix host info
        return self.info.get('zabbix', {})

    @zabbix_info.setter
    def zabbix_info(self, host):  # Save zabbix host info
        self.save_info('zabbix', host, save=False)

    def save_zabbix_info(self, zxhost=None):
        if zxhost is not None:
            self.zabbix_info = zxhost
        self.save(update_fields=('enc_info', 'changed'))

    @property
    def external_zabbix_info(self):  # Return zabbix host info
        return self.info.get('external_zabbix', {})

    @external_zabbix_info.setter
    def external_zabbix_info(self, host):  # Save zabbix host info
        self.save_info('external_zabbix', host, save=False)

    def save_external_zabbix_info(self, zxhost=None):
        if zxhost is not None:
            self.external_zabbix_info = zxhost
        self.save(update_fields=('enc_info', 'changed'))

    @property
    def zabbix_sync(self):  # Create in zabbix?
        return not self.json.get('do_not_inventory', False)

    @zabbix_sync.setter
    def zabbix_sync(self, value):  # Enable/Disable zabbix synchronization
        if value:
            self.delete_item('do_not_inventory', save=False)
        else:
            self.save_item('do_not_inventory', True, save=False)

    monitored_internal = zabbix_sync

    def is_zabbix_sync_active(self):
        """Return do_not_inventory status from json_active"""
        if self.is_deployed():
            return not self.json_active.get('do_not_inventory', False)
        else:
            return 'hostid' in self.zabbix_info

    @property
    def external_zabbix_sync(self):  # Create in external zabbix?
        return self.internal_metadata.get('monitored', self.zabbix_sync)

    @external_zabbix_sync.setter
    def external_zabbix_sync(self, value):
        self.save_metadata('monitored', value, save=False)

    monitored = external_zabbix_sync

    def is_external_zabbix_sync_active(self):
        """Return external zabbix sync status from json_active"""
        if self.is_deployed():
            return self.json_active.get('internal_metadata', {}).get('monitored', self.is_zabbix_sync_active())
        else:
            return 'hostid' in self.external_zabbix_info

    @property
    def monitoring_hostgroups(self):  # Custom VM hostgroups
        hostgroups = self.internal_metadata.get('mon_hostgroups', None)
        if hostgroups:
            return hostgroups.split(',')
        return []

    @monitoring_hostgroups.setter
    def monitoring_hostgroups(self, value):
        self.save_metadata('mon_hostgroups', ','.join(value), save=False)

    @property
    def monitoring_templates(self):  # Custom VM templates
        templates = self.internal_metadata.get('mon_templates', None)
        if templates:
            return templates.split(',')
        return []

    @monitoring_templates.setter
    def monitoring_templates(self, value):
        self.save_metadata('mon_templates', ','.join(value), save=False)

    @property
    def monitoring_ip(self):
        return self.internal_metadata.get('mon_ip', '')

    @monitoring_ip.setter
    def monitoring_ip(self, value):
        if value is None:
            value = ''
        self.save_metadata('mon_ip', str(value), save=False)

    @property
    def monitoring_dns(self):
        return self.internal_metadata.get('mon_dns', self.hostname)

    @monitoring_dns.setter
    def monitoring_dns(self, value):
        if value is None:
            self.delete_metadata('mon_dns', save=False)
        else:
            self.save_metadata('mon_dns', str(value), save=False)

    @property
    def monitoring_port(self):
        return self.internal_metadata.get('mon_port', self.dc.settings.MON_ZABBIX_HOST_VM_PORT)

    @monitoring_port.setter
    def monitoring_port(self, value):
        if value is None:
            self.delete_metadata('mon_port', save=False)
        else:
            self.save_metadata('mon_port', value, save=False)

    @property
    def monitoring_useip(self):
        return self.internal_metadata.get('mon_useip', self.dc.settings.MON_ZABBIX_HOST_VM_USEIP)

    @monitoring_useip.setter
    def monitoring_useip(self, value):
        if value is None:
            self.delete_metadata('mon_useip', save=False)
        else:
            self.save_metadata('mon_useip', value, save=False)

    @property
    def monitoring_proxy(self):
        return self.internal_metadata.get('mon_proxy', self.dc.settings.MON_ZABBIX_HOST_VM_PROXY)

    @monitoring_proxy.setter
    def monitoring_proxy(self, value):
        if value is None:
            self.delete_metadata('mon_proxy', save=False)
        else:
            self.save_metadata('mon_proxy', str(value), save=False)

    @property  # Return node hostname
    def node_hostname(self):
        if self.node:
            return self.node.hostname
        return self.node

    @property  # get VM zpool
    def zpool(self):
        return self.json.get('zpool', Node.ZPOOL)

    @zpool.setter
    def zpool(self, value):
        self.save_item('zpool', str(value), save=False)

    @staticmethod
    def calculate_cpu_cap_from_vcpus(vcpus):
        """Simple calculation of cpu_cap from vCPUs count"""
        if vcpus:
            if vcpus == 1:
                cpu_burst = settings.VMS_VM_CPU_BURST_DEFAULT / 2
            else:
                cpu_burst = settings.VMS_VM_CPU_BURST_DEFAULT

            return int(vcpus * settings.VMS_VM_CPU_BURST_RATIO * 100) + cpu_burst
        else:
            return 0

    @staticmethod
    def calculate_cpu_count_from_cpu_cap(cpu_cap):
        """Return CPU count suitable for resource accounting
        This is _not_ an inverse function of calculate_cpu_cap_from_vcpus()"""
        if cpu_cap:
            vcpus = int((int(cpu_cap) - settings.VMS_VM_CPU_BURST_DEFAULT) / (settings.VMS_VM_CPU_BURST_RATIO * 100))

            if vcpus:
                return vcpus
            else:
                return 1  # this means that we have some small cpu_cap
        else:
            return 0

    @classmethod
    def calculate_cpu_count_from_vcpus(cls, vcpus):
        """Always go through the same calculation and get the CPU count from cpu_cap"""
        return cls.calculate_cpu_count_from_cpu_cap(cls.calculate_cpu_cap_from_vcpus(vcpus))

    @classmethod
    def _get_cpu_zone(cls, json):
        """Return CPU count suitable for resource accounting (based on cpu_cap)"""
        return cls.calculate_cpu_count_from_cpu_cap(json.get('cpu_cap', None))

    @property
    def cpu_type(self):
        if self.is_kvm():
            return self.json.get('cpu_type', self.CPU_TYPE_QEMU)
        else:
            return ''

    @cpu_type.setter
    def cpu_type(self, value):
        if self.is_kvm():
            self.save_item('cpu_type', value, save=False)

    @property
    def cpu_cap(self):
        return self.json.get('cpu_cap', 0)

    @cpu_cap.setter
    def cpu_cap(self, value):
        raise NotImplementedError('cpu_cap must be set only via vcpus')

    @property  # Return number of vcpus (real for KVM and a CPU count for zones)
    def vcpus(self):
        if self.is_hvm():
            return self.json.get('vcpus', 0)
        else:
            return self._get_cpu_zone(self.json)

    @vcpus.setter  # Set json.vcpus
    def vcpus(self, value):
        cpu_cap = self.calculate_cpu_cap_from_vcpus(value)

        if self.is_hvm():
            self.save_items(vcpus=value, cpu_cap=cpu_cap, save=False)
        else:
            self.save_item('cpu_cap', cpu_cap, save=False)

    @property  # Return number of vcpus
    def vcpus_active(self):
        if self.is_hvm():
            return self.json_active.get('vcpus', 0)
        else:
            return self._get_cpu_zone(self.json_active)

    @property  # Return RAM size in MB
    def ram(self):
        if self.is_hvm():
            return self.json.get('ram', 0)
        else:
            return self.json.get('max_physical_memory', 0)

    @ram.setter  # Set json.ram
    def ram(self, value):
        max_swap = int(value * settings.VMS_VM_SWAP_MULTIPLIER)  # We assume that the multiplier is >= 1

        if max_swap < 256:
            max_swap = 256

        if self.is_hvm():
            max_physical_memory = value + settings.VMS_VM_KVM_MEMORY_OVERHEAD

            if max_swap < max_physical_memory:
                max_swap = max_physical_memory

            self.save_items(ram=value, max_physical_memory=max_physical_memory, max_swap=max_swap, max_locked_memory=max_physical_memory, save=False)
        else:
            self.save_items(max_physical_memory=value, max_swap=max_swap, save=False)

    @property  # Return RAM size in MB
    def ram_active(self):
        if self.is_hvm():
            return self.json_active.get('ram', 0)
        else:
            return self.json_active.get('max_physical_memory', 0)

    @property
    def ram_overhead(self):
        if self.is_hvm():
            return settings.VMS_VM_KVM_MEMORY_OVERHEAD
        else:
            return 0

    @property
    def disk(self):  # Aggregated disk size
        return sum(self.get_disks(zpool=None, active=False).values())

    @property
    def disk_active(self):  # Aggregated disk size
        return sum(self.get_disks(zpool=None, active=True).values())

    @property
    def ips(self):
        return self.json_get_ips()

    @property
    def ips_active(self):
        return self.json_active_get_ips()

    @property
    def primary_ip(self):
        for nic in self.json_get_nics():
            if is_ip(nic) and nic.get('primary', False):
                return nic['ip']

        raise LookupError('Primary IP not found')

    @property
    def primary_ip_active(self):
        for nic in self.json_active_get_nics():
            if is_ip(nic) and nic.get('primary', False):
                return nic['ip']

        raise LookupError('Primary IP not found')

    @property  # Return installed boolean
    def installed(self):
        return self.internal_metadata.get('installed', None)

    @installed.setter  # Set json.internal_metadata.installed
    def installed(self, value):
        self.save_metadata('installed', value, save=False)

    @property  # Return size limit for all snapshots
    def snapshot_size_limit(self):
        return self.internal_metadata.get('snapshot_size_limit', None)

    @snapshot_size_limit.setter  # Set json.internal_metadata.snapshot_size_limit
    def snapshot_size_limit(self, value):
        if value is None:  # SmartOS doesn't like null in internal_metadata
            self.delete_metadata('snapshot_size_limit', save=False)
        else:
            self.save_metadata('snapshot_size_limit', value, save=False)

    @property  # Return limit for manual snapshots
    def snapshot_limit_manual(self):
        return self.internal_metadata.get('snapshot_limit_manual', None)

    @snapshot_limit_manual.setter  # Set json.internal_metadata.snapshot_limit_manual
    def snapshot_limit_manual(self, value):
        if value is None:  # SmartOS doesn't like null in internal_metadata
            self.delete_metadata('snapshot_limit_manual', save=False)
        else:
            self.save_metadata('snapshot_limit_manual', value, save=False)

    @property  # Return limit for auto snapshots
    def snapshot_limit_auto(self):
        return self.internal_metadata.get('snapshot_limit_auto', None)

    @snapshot_limit_auto.setter  # Set json.internal_metadata.snapshot_limit_auto
    def snapshot_limit_auto(self, value):
        if value is None:  # SmartOS doesn't like null in internal_metadata
            self.delete_metadata('snapshot_limit_auto', save=False)
        else:
            self.save_metadata('snapshot_limit_auto', value, save=False)

    @property
    def cpu_shares(self):
        return self.json.get('cpu_shares', 100)

    @cpu_shares.setter
    def cpu_shares(self, value):
        self.save_item('cpu_shares', value, save=False)

    @property
    def routes(self):
        return self.json.get('routes', {})

    @routes.setter
    def routes(self, value):
        if not self.is_hvm():
            self.save_item('routes', value or {}, save=False)

    @property
    def dns_domain(self):
        return self.json.get('dns_domain', '')

    @dns_domain.setter
    def dns_domain(self, value):
        if not self.is_hvm():
            self.save_item('dns_domain', value or '', save=False)

    @property
    def resolvers(self):
        return self.json.get('resolvers', [])

    @resolvers.setter
    def resolvers(self, value):
        self.save_item('resolvers', value, save=False)

    @property
    def maintain_resolvers(self):
        return self.json.get('maintain_resolvers', False)

    @maintain_resolvers.setter
    def maintain_resolvers(self, value):
        if not self.is_hvm():
            self.save_item('maintain_resolvers', value, save=False)

    @property
    def zfs_io_priority(self):
        return self.json.get('zfs_io_priority', 100)

    @zfs_io_priority.setter
    def zfs_io_priority(self, value):
        self.save_item('zfs_io_priority', value, save=False)

    @property
    def vga(self):
        return self.json.get('vga', 'std')

    @vga.setter
    def vga(self, value):
        if self.is_kvm():
            self.save_item('vga', value, save=False)

    @classmethod
    def _remove_reserved_mdata_keys(cls, data):
        hide = cls.RESERVED_MDATA_KEYS

        for k in data.keys():
            if k in hide:
                del data[k]

        return data

    @property
    def mdata(self):
        return self._remove_reserved_mdata_keys(self.customer_metadata)

    @mdata.setter
    def mdata(self, value):
        self.customer_metadata = self._remove_reserved_mdata_keys(value)

    @property
    def lifetime(self):
        return int(timezone.now().strftime('%s')) - int(self.created.strftime('%s'))

    @property
    def last_cdimage(self):  # Return last used ISO image name or None
        return self.info.get('last_cdimage', None)

    @last_cdimage.setter
    def last_cdimage(self, value):  # Save last used ISO image name
        self.save_info('last_cdimage', value, save=True)

    @property
    def brand(self):
        return self.json.get('brand', 'kvm')

    def revert_active(self, json_only=False, revert_owner=True, revert_template=True):
        """Replace json with json_active to mimic VM configuration on hypervisor"""
        self.lock()
        self.json = json_active = self.json_active

        if json_only:
            return

        internal_metadata = json_active.get('internal_metadata', {})
        self.hostname = json_active.get('hostname', self.hostname)
        self.alias = internal_metadata.get('alias', self.alias)

        if revert_owner:
            owner_id = json_active.get('owner_uuid', str(self.owner.id))
            if owner_id != str(self.owner.id) and owner_id:
                try:
                    self.owner = User.objects.get(id=int(owner_id))
                except User.DoesNotExist:
                    pass

        if revert_template:
            template_name = internal_metadata.get('template', None)
            if template_name != getattr(self.template, 'name', None):
                if template_name:
                    try:
                        self.template = VmTemplate.objects.get(name=template_name)
                    except VmTemplate.DoesNotExist:
                        pass
                else:
                    self.template = None

    @property
    def qga_socket_path(self):
        if self.is_hvm():
            json = self.json_active

            if settings.VMS_VM_QEMU_GUEST_AGENT_SOCKET in json.get('qemu_extra_opts', '') or \
                    settings.VMS_VM_QEMU_GUEST_AGENT_SOCKET in json.get('bhyve_extra_opts', ''):
                return '/%s/root%s' % (json['zfs_filesystem'], settings.VMS_VM_QEMU_GUEST_AGENT_SOCKET)

        return None

    def get_image_uuids(self, zpool=None):
        """Return set of image_uuids for currently used/required images by this VM"""
        vm_disks = self.json_get_disks()

        if self.is_deployed():
            vm_disks += self.json_active_get_disks()

        if zpool:
            def disk_filter(disk):
                return 'image_uuid' in disk and disk.get('zpool', None) == zpool
        else:
            def disk_filter(disk):
                return 'image_uuid' in disk

        return {dsk['image_uuid'] for dsk in vm_disks if disk_filter(dsk)}

    def get_vm_nics(self):
        vm_nics = self.json_get_nics()

        if self.is_deployed():
            vm_nics += self.json_active_get_nics()

        return vm_nics

    def get_network_uuids(self):
        """Return set of network_uuids for currently used/required subnets by this VM"""
        return {nic['network_uuid'] for nic in self.get_vm_nics()}

    def get_nic_config(self, net_uuid):
        """Return raw nic config for specified network uuid"""
        for nic in self.get_vm_nics():
            if nic['network_uuid'] == net_uuid:
                return nic
        return None

    def is_slave_vm(self):
        """Return True if this a VM object associated with SlaveVM"""
        return hasattr(self, 'slavevm')

    def add_slave_vm(self, vm):
        """Add VM's uuid into list of slave VM uuids"""
        slave_vms = set(self.slave_vms)
        slave_vms.add(UUID(vm.uuid))
        self.slave_vms = slave_vms

    def delete_slave_vm(self, vm):
        """Remove VM's uuid from list of slave VM uuids"""
        slave_vms = set(self.slave_vms)
        slave_vms.remove(UUID(vm.uuid))
        self.slave_vms = slave_vms

    @property
    def locked(self):
        """Return True if VM has slave VMs"""
        return bool(self.slave_vms)

    @property
    def size_snapshots(self):
        if self.is_slave_vm():
            vm = self.slavevm.master_vm
        else:
            vm = self

        from vms.models.snapshot import Snapshot
        return Snapshot.get_total_vm_size(vm)

    @property
    def size_backups(self):
        from vms.models.backup import Backup
        return Backup.get_total_vm_size(self)

    @property
    def tag_list(self):
        return self.tags.names()
