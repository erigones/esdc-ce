from django.db import models, transaction
from django.utils import timezone, six
from django.utils.translation import ugettext_noop, ugettext_lazy as _
from django.core.cache import cache
from django.conf import settings

import decimal
import operator
from functools import reduce

# noinspection PyProtectedMember
from vms.models.base import _JsonPickleModel, _StatusModel, _UserTasksModel, _OSType
from vms.models.dc import Dc
from vms.models.storage import Storage, NodeStorage
from gui.models import User


NODES_ALL_KEY = 'nodes_list'
NODES_ALL_EXPIRES = 300
NICTAGS_ALL_KEY = 'nictag_list'
NICTAGS_ALL_EXPIRES = None


class Node(_StatusModel, _JsonPickleModel, _UserTasksModel):
    """
    Node (host) object.
    """
    _esysinfo = ('sysinfo', 'diskinfo', 'zpools', 'nictags')
    _vlan_id = None

    ZPOOL = 'zones'
    # Used in NodeStorage.size_vms
    VMS_SIZE_TOTAL_KEY = 'vms-size-total:%s'  # %s = zpool.id (NodeStorage)
    VMS_SIZE_DC_KEY = 'vms-size-dc:%s:%s'  # %s = dc.id:zpool.id (NodeStorage)

    OFFLINE = 1
    ONLINE = 2
    UNREACHABLE = 3
    UNLICENSED = 9
    STATUS_DB = (  # Do not change the order here
        (ONLINE, ugettext_noop('online')),
        (OFFLINE, ugettext_noop('maintenance')),
        (UNREACHABLE, ugettext_noop('unreachable')),
        (UNLICENSED, ugettext_noop('unlicensed')),
    )
    STATUS = STATUS_DB[:2]
    STATUS_OPERATIONAL = frozenset([ONLINE])
    STATUS_AVAILABLE_MONITORING = frozenset([ONLINE, OFFLINE, UNREACHABLE])

    _pk_key = 'node_uuid'  # _UserTasksModel
    _log_name_attr = 'hostname'  # _UserTasksModel
    _cache_status = True  # _StatusModel
    _storage = None  # Local storage cache
    _ns = None  # Local node storage cache
    _ip = None  # Related IPAddress object

    # Inherited: status_change, created, changed, json
    uuid = models.CharField(_('UUID'), max_length=36, primary_key=True)
    hostname = models.CharField(_('Hostname'), max_length=128, unique=True)
    address = models.CharField(_('Address'), max_length=64)
    status = models.SmallIntegerField(_('Status'), choices=STATUS_DB, default=OFFLINE, db_index=True)
    owner = models.ForeignKey(User, verbose_name=_('Owner'), default=settings.VMS_NODE_USER_DEFAULT,
                              on_delete=models.PROTECT)
    dc = models.ManyToManyField(Dc, through='DcNode', verbose_name=_('Datacenter'), blank=True)
    config = models.TextField(_('Config'), blank=True)
    cpu = models.PositiveIntegerField(_('CPUs'), help_text=_('Total number of CPUs (cores).'))
    ram = models.PositiveIntegerField(_('RAM (MB)'), help_text=_('Total RAM size in MB.'))
    cpu_coef = models.DecimalField(_('CPUs coefficient'), max_digits=4, decimal_places=2, default='1',
                                   help_text=_('Coefficient for calculating the the total number of virtual CPUs.'))
    ram_coef = models.DecimalField(_('RAM coefficient'), max_digits=4, decimal_places=2, default='1',
                                   help_text=_('Coefficient for calculating the maximum amount of '
                                               'memory for virtual machines.'))
    cpu_free = models.IntegerField(_('Free CPUs'), default=0, editable=False)
    ram_free = models.IntegerField(_('Free RAM (MB)'), default=0, editable=False)
    is_compute = models.BooleanField(_('Compute'), default=True)
    is_backup = models.BooleanField(_('Backup'), default=False)
    is_head = models.BooleanField(_('Head node'), default=False)
    note = models.TextField(_('Note'), blank=True)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Node')
        verbose_name_plural = _('Nodes')

    def __unicode__(self):
        return '%s' % self.hostname

    @property
    def alias(self):  # task log requirement
        return self.hostname

    @property
    def name(self):  # task log requirement
        return self.hostname

    @property
    def web_data(self):
        """Return dict used in html templates"""
        return {
            'hostname': self.hostname,
            'status': self.status,
            'owner': self.owner.username,
            'is_compute': self.is_compute,
            'is_backup': self.is_backup,
            'note': self.note,
            'cpu_coef': self.cpu_coef,
            'ram_coef': self.ram_coef,
            'monitoring_templates': self.monitoring_templates,
            'monitoring_hostgroups': self.monitoring_hostgroups,
        }

    @property
    def cpu_total(self):
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        return int(self.cpu * float(self.cpu_coef))

    @property
    def ram_total(self):
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        return int(self.ram * float(self.ram_coef))

    @property
    def _sysinfo(self):
        return self.json.get('sysinfo', {})

    @property
    def platform_version(self):
        return self._sysinfo.get('Live Image', None)

    def platform_version_short(self):
        version = self.platform_version

        if not version:
            return 0

        return int(version[:6])

    @property
    def dc_name(self):
        return self._sysinfo.get('Datacenter Name', '')

    @property
    def domain_name(self):
        return self.hostname.partition('.')[2]

    @property
    def cpu_sockets(self):
        return self._sysinfo.get('CPU Physical Cores', None)

    @property
    def sysinfo(self):
        """System information displayed in gui/api"""
        x = self._sysinfo
        wanted = ('Boot Time', 'Manufacturer', 'Product', 'Serial Number', 'SKU Number', 'HW Version', 'HW Family',
                  'Setup', 'VM Capable', 'CPU Type', 'CPU Virtualization', 'CPU Physical Cores')
        return {i: x.get(i, '') for i in wanted}

    @property
    def diskinfo(self):
        return self.json.get('diskinfo', {})

    @property
    def zpools(self):
        return self.json.get('zpools', {})

    @property
    def boottime(self):
        return int(self._sysinfo.get('Boot Time', 0))

    @property
    def network_interfaces(self):
        """Network Interfaces"""
        return self._sysinfo.get('Network Interfaces', {})

    @property
    def virtual_network_interfaces(self):
        """Virtual Network Interfaces"""
        return self._sysinfo.get('Virtual Network Interfaces', {})

    @property
    def network_aggregations(self):
        """Network aggregations"""
        return self._sysinfo.get('Link Aggregations', {})

    @property
    def networking(self):
        """Complete network information"""
        return {
            'Network Interfaces': self.network_interfaces,
            'Virtual Network Interfaces': self.virtual_network_interfaces,
            'Link Aggregations': self.network_aggregations,
            'NIC Tags': self.nictags
        }

    @property
    def used_nics(self):
        """NICs that are being used by node.

        This is determined by checking if NIC has IPv4 address associated with it.
        """
        all_nics = self.network_interfaces.copy()
        all_nics.update(self.virtual_network_interfaces)

        return {iface: prop for iface, prop in six.iteritems(all_nics) if prop.get('ip4addr')}

    @property
    def api_sysinfo(self):
        """Complete compute node OS info"""
        sysinfo = self.sysinfo
        sysinfo['networking'] = self.networking
        sysinfo['zpools'] = self.zpools
        sysinfo['disks'] = self.diskinfo

        return sysinfo

    @property
    def zpool(self):
        """Default zpool name, defined on node"""
        return self._sysinfo.get('Zpool', None)

    @property
    def zpool_size(self):
        """Default zpool size"""
        return int(self._sysinfo.get('Zpool Size in GiB', 0)) * 1024

    @property
    def storage(self):
        """Default local storage"""
        if not self._storage:  # cache
            if self.zpool:
                try:
                    self._ns = NodeStorage.objects.select_related('storage').get(node=self, zpool=self.zpool)
                    self._storage = self._ns.storage
                except models.ObjectDoesNotExist:
                    name = ('%s@%s' % (self.zpool, self.hostname))[:64]
                    self._storage = Storage(size=self.zpool_size, owner=self.owner, access=Storage.PUBLIC,
                                            name=name, alias=self.zpool, desc='Default local storage pool')
            else:
                self._storage = Storage(size_coef='1.0', size=0, type=Storage.LOCAL)
        return self._storage

    @property
    def disk(self):
        return self.storage.size

    @disk.setter
    def disk(self, value):
        self.storage.size = value

    @property
    def disk_free(self):
        return self.storage.size_free

    @disk_free.setter
    def disk_free(self, value):  # The value here is the total size of local disk - (backup + snap + vms size)
        if self._ns:
            # TODO: fix ns.size_images implementation and subtract it too
            vms_size = (self.storage.size_total - self._ns.size_backups - self._ns.size_snapshots -
                        self._ns.size_rep_snapshots - value)
            cache.set(self.VMS_SIZE_TOTAL_KEY % self._ns.pk, vms_size)
        self.storage.size_free = value

    @property
    def disk_coef(self):
        return self.storage.size_coef

    def is_online(self):
        return self.status == self.ONLINE

    def is_offline(self):
        return self.status == self.OFFLINE

    def is_unreachable(self):
        return self.status == self.UNREACHABLE

    def is_unlicensed(self):
        return self.status == self.UNLICENSED

    @property
    def ip_address(self):
        from vms.models.ipaddress import IPAddress, Subnet  # Circular imports

        if self._ip is None:
            self._ip = IPAddress.objects.get(subnet=Subnet.objects.get(name=settings.VMS_NET_ADMIN),
                                             ip=self.address, usage=IPAddress.NODE)
        return self._ip

    @ip_address.setter
    def ip_address(self, address):
        from vms.models.ipaddress import IPAddress, Subnet  # Circular imports

        self._ip = IPAddress(subnet=Subnet.objects.get(name=settings.VMS_NET_ADMIN),
                             ip=address, usage=IPAddress.NODE, note=self.hostname)
        self.address = address

    @property
    def vlan_id(self):
        assert self._vlan_id is not None, 'vlan_id is available only during node initialization'
        return self._vlan_id

    @property
    def esysinfo(self):  # esysinfo is a dictionary consisting of 3 items: sysinfo, diskinfo, zpools
        _json = self.json
        return {i: _json.get(i, {}) for i in self._esysinfo}

    @esysinfo.setter
    def esysinfo(self, value):  # esysinfo is a dictionary consisting of 3 items: sysinfo, diskinfo, zpools
        _json = self.json
        for i in self._esysinfo:
            _json[i] = value[i]
        self.json = _json

    @property
    def sshkey(self):
        return self.json.get('sshkey', None)

    @sshkey.setter
    def sshkey(self, value):
        self.save_item('sshkey', value, save=False)

    @property
    def authorized_keys(self):
        return self.json.get('authorized_keys', '')

    @authorized_keys.setter
    def authorized_keys(self, value):
        self.save_item('authorized_keys', value, save=False)

    def save_authorized_keys(self, value):
        self.authorized_keys = value
        self.save(update_resources=False, update_fields=('enc_json', 'changed'))

    @property
    def nictags(self):
        return self.json.get('nictags', [])

    @property
    def lifetime(self):
        return int(timezone.now().strftime('%s')) - int(self.created.strftime('%s'))

    @property  # Return host name used as Zabbix alias
    def zabbix_name(self):
        return self.hostname

    @property
    def zabbix_id(self):
        return self.uuid

    @property
    def zabbix_info(self):  # Return zabbix host info
        return self.json.get('zabbix', {})

    @zabbix_info.setter
    def zabbix_info(self, host):  # Save zabbix host info
        self.save_item('zabbix', host, save=False)

    def save_zabbix_info(self, zxhost=None):
        if zxhost is not None:
            self.zabbix_info = zxhost
        self.save(update_resources=False, update_fields=('enc_json', 'changed'))

    @property
    def zabbix_sync(self):  # Create in zabbix?
        return True

    @zabbix_sync.setter
    def zabbix_sync(self, value):  # Enable/Disable zabbix synchronization
        pass

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
    def monitoring_hostgroups(self):  # Custom VM hostgroups
        return self.internal_metadata.get('mon_hostgroups', [])

    @monitoring_hostgroups.setter
    def monitoring_hostgroups(self, value):
        self.save_metadata('mon_hostgroups', value, save=False)

    @property
    def monitoring_templates(self):  # Custom VM templates
        return self.internal_metadata.get('mon_templates', [])

    @monitoring_templates.setter
    def monitoring_templates(self, value):
        self.save_metadata('mon_templates', value, save=False)

    @classmethod
    def choose(cls, vm):
        """Choose appropriate node for a new VM"""
        return DcNode.choose_node(vm.dc, vm)

    @classmethod
    def all(cls, clear_cache=False):
        """Return list of all nodes from cache"""
        if clear_cache:
            return cache.delete(NODES_ALL_KEY)

        nodes = cache.get(NODES_ALL_KEY)

        if not nodes:
            nodes = cls.objects.only('uuid', 'hostname', 'status', 'address', 'is_compute', 'is_backup', 'is_head')\
                               .order_by('hostname')
            cache.set(NODES_ALL_KEY, nodes, NODES_ALL_EXPIRES)

        return nodes

    @classmethod
    def all_nictags(cls, clear_cache=False):
        """Return dictionary with of nictags {name:type}"""
        if clear_cache:
            cache.delete(NICTAGS_ALL_KEY)

        nictags = cache.get(NICTAGS_ALL_KEY)

        if not nictags:
            nodes = cls.objects.all()
            nictags = {}

            for node in nodes:
                for nic in node.nictags:
                    nic_name = nic['name']
                    nic_type = nic['type'].replace('aggr', 'normal')
                    # if nictag name is already present and types are not equal
                    if nic_name in nictags and nic_type != nictags[nic_name]:
                        raise ValueError('Duplicate NIC tag name with different type exists on another compute node!')

                    nictags[nic_name] = nic_type

            cache.set(NICTAGS_ALL_KEY, nictags, NICTAGS_ALL_EXPIRES)

        return nictags

    @classmethod
    def all_nictags_choices(cls):
        """Return set of tuples that are used as choices in nictag field in NetworkSerializer"""
        return sorted([(name, '%s (%s)' % (name, typ)) for name, typ in six.iteritems(cls.all_nictags())])

    @property
    def _initializing_key(self):
        return 'node:%s:initializing' % self.uuid

    def is_initializing(self):
        """Return True if node is being initialized by api.node.sysinfo.tasks.node_sysinfo_cb"""
        return bool(cache.get(self._initializing_key))

    def set_initializing(self):
        cache.set(self._initializing_key, True, 600)

    def del_initializing(self):
        cache.delete(self._initializing_key)

    def parse_sysinfo(self, esysinfo, update_ip=False):
        """Get useful information from sysinfo"""
        self.config = esysinfo.pop('config', '')
        self.sshkey = esysinfo.pop('sshkey', '')
        self.esysinfo = esysinfo
        sysinfo = self._sysinfo
        self.hostname = sysinfo['Hostname']

        if update_ip:
            # First, try the 'admin0' VNIC
            admin_iface = sysinfo.get('Virtual Network Interfaces', {}).get('admin0', {})
            ip = admin_iface.get('ip4addr', None)

            # Then, walk through all NICs and search for the 'admin' NIC tag
            if not ip:
                for iface, iface_info in sysinfo['Network Interfaces'].items():
                    if 'admin' in iface_info.get('NIC Names', ()):
                        admin_iface = iface_info
                        ip = admin_iface.get('ip4addr', None)
                        break

            assert ip, 'Node IP Address not found in sysinfo output'

            self._vlan_id = admin_iface.get('VLAN', 0)  # Used by api.system.init.init_mgmt()
            self.ip_address = ip

    def sysinfo_changed(self, esysinfo):
        """Return True if sysinfo changed"""
        new_esysinfo = esysinfo.copy()
        config = new_esysinfo.pop('config', '')
        new_esysinfo.pop('sshkey', None)
        return not(self.esysinfo == new_esysinfo and self.config == config)

    def sshkey_changed(self, esysinfo):
        """Return True if compute node's public SSH key has changed"""
        return self.sshkey != esysinfo.get('sshkey', '')

    @classmethod
    def create_from_sysinfo(cls, uuid, esysinfo, status=ONLINE, is_head=False):
        """Create new node from esysinfo"""
        node = cls(uuid=uuid, status=status, is_head=is_head)
        node.parse_sysinfo(esysinfo, update_ip=True)
        node.set_initializing()
        node.save(sync_json=True, update_resources=True, zpool_create=True, clear_cache=True)

        # Create default association with Datacenter
        if settings.VMS_NODE_DC_DEFAULT:
            dc = Dc.objects.get_by_id(settings.VMS_NODE_DC_DEFAULT)
            dc_node = DcNode(dc=dc, node=node, strategy=DcNode.SHARED)  # Shared strategy should copy Node resources
            dc_node.save(update_resources=True)
            # Attach local node storage to Datacenter
            if node._ns:
                node._ns.dc.add(dc)

        return node

    def update_from_sysinfo(self, esysinfo):
        """Update node from sysinfo and /usbkey/config output"""
        current_zpools = self.zpools
        self.parse_sysinfo(esysinfo, update_ip=False)
        new_zpools = self.zpools
        self.save(sync_json=True, update_resources=True, zpool_update=True, clear_cache=True,
                  zpools_update=(current_zpools != new_zpools))

    @property
    def ram_kvm_overhead(self):
        return self.json.get('ram_kvm_overhead', 0)

    @ram_kvm_overhead.setter
    def ram_kvm_overhead(self, value):
        self.save_item('ram_kvm_overhead', value, save=False)

    @property
    def resources(self):
        """Return tuple with total (cpu, ram, disk) resources"""
        # We are working with decimal objects and rounding everything down
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        # The total local disk size should not include backups and snapshots
        # TODO: fix ns.size_images and subtract it too
        disk_size_total = self.storage.size_total
        if self._ns:
            disk_size_total -= self._ns.size_backups + self._ns.size_snapshots + self._ns.size_rep_snapshots

        return self.cpu * float(self.cpu_coef), self.ram * float(self.ram_coef), disk_size_total

    def get_used_resources(self, dc):
        """Count used node resources in DC"""
        cpu, ram, disk = 0, 0, 0

        for vm in self.vm_set.filter(dc=dc):
            vm_cpu, vm_ram, vm_disk = vm.get_cpu_ram_disk(zpool=self.zpool, ram_overhead=True)
            cpu += vm_cpu
            ram += vm_ram
            disk += vm_disk

        return int(cpu), int(ram), int(disk)

    def get_free_resources(self, cpu, ram, disk, dc=None, dc_exclude=None, dcs_exclude=None):
        """Count free node resources according to parameters"""
        if dc:
            vms = self.vm_set.filter(dc=dc)
        else:
            vms = self.vm_set.all()

        if dcs_exclude:
            vms = vms.exclude(dc__in=dcs_exclude)
        if dc_exclude:
            vms = vms.exclude(dc=dc_exclude)

        for vm in vms:
            vm_cpu, vm_ram, vm_disk = vm.get_cpu_ram_disk(zpool=self.zpool, ram_overhead=True)
            cpu -= vm_cpu
            ram -= vm_ram
            disk -= vm_disk

        return int(cpu), int(ram), int(disk)

    def get_ram_kvm_overhead(self, dc=None):
        """Get KVM_MEMORY_OVERHEAD for all VMs on this node (and DC)"""
        if dc:
            vms = self.vm_set.filter(dc=dc)
        else:
            vms = self.vm_set

        vms_count = vms.filter(ostype__in=_OSType.KVM).count()  # FIXME: no index on ostype

        return vms_count * settings.VMS_VM_KVM_MEMORY_OVERHEAD

    def update_resources(self, save=False):
        """Update free node resources from VM parameters defined on node"""
        if save:
            return self.save(update_resources=True)

        self.cpu_free, self.ram_free, self.disk_free = self.get_free_resources(*self.resources)
        self.ram_kvm_overhead = self.get_ram_kvm_overhead()

    def get_dc_node(self, dc):
        """Helper for VmSerializer"""
        return DcNode.objects.get(dc=dc, node=self)

    def get_node_storage(self, dc, zpool):
        """Helper for VmSerializer"""
        return NodeStorage.objects.select_related('storage').get(node=self, zpool=zpool, dc=dc)

    def get_node_storages(self, dc, zpools):
        """Helper for VmSerializer"""
        return NodeStorage.objects.select_related('storage').filter(node=self, zpool__in=zpools, dc=dc)

    def sync_json(self):
        """Sync outside attributes according to json."""
        sysinfo = self._sysinfo
        self.cpu = int(sysinfo.get('CPU Total Cores', 0))
        self.ram = int(sysinfo.get('MiB of Memory', 0))
        self.disk = self.zpool_size

    def save(self, sync_json=False, update_resources=True, zpool_update=False, zpool_create=False,
             zpools_update=False, clear_cache=False, save_ip=False, **kwargs):
        """Update free resources before saving"""
        if sync_json:
            self.sync_json()
            update_resources = True

        if update_resources:
            self.update_resources(save=False)
            zpool_update = True

        if self._orig_status == self.status:
            status_changed = False
        else:
            status_changed = True

        # save!
        with transaction.atomic():
            ret = super(Node, self).save(**kwargs)

            if save_ip and self._ip:
                self._ip.save()

            # this may eventually block the creation or update of the node from sysinfo
            if clear_cache or status_changed:
                self.all(clear_cache=True)
                self.all_nictags(clear_cache=True)

        if self.zpool and (zpool_update or zpool_create):
            self.storage.save()  # size parameters were updated during update_resources()
            if zpool_create or not self._ns:
                self._ns = NodeStorage(node=self, storage=self.storage, zpool=self.zpool)
                self._ns.save()

        if zpools_update:  # Maybe a zpool other than zones was added, removed or modified
            node_zpools = self.zpools
            node_zpools.pop(self.ZPOOL)

            for ns in NodeStorage.objects.select_related('storage').filter(node=self, zpool__in=node_zpools.keys()):
                try:
                    zpool_size = node_zpools[ns.zpool]['size']
                except KeyError:
                    continue

                if ns.storage.size != zpool_size:
                    with transaction.atomic():
                        ns.storage.size = zpool_size
                        ns.storage.save()
                        ns.save()

        if update_resources:
            DcNode.update_all(node=self)

        return ret

    def save_status(self, new_status=None, **kwargs):
        kwargs['update_resources'] = False
        return super(Node, self).save_status(new_status=new_status, **kwargs)

    def delete(self, **kwargs):
        """Clear list of all nodes from cache"""
        ret = super(Node, self).delete(**kwargs)
        self.all(clear_cache=True)
        self.all_nictags(clear_cache=True)
        return ret

    def _get_queue(self, speed):
        """Return the celery queue name"""
        return speed + '.' + self.hostname

    @property
    def all_queues(self):
        return [self._get_queue(i) for i in ('fast', 'slow', 'image', 'backup')]

    @property
    def fast_queue(self):
        # fast queue is always available on compute and backup nodes
        return self._get_queue('fast')

    @property
    def slow_queue(self):
        assert self.is_compute, 'Node compute capability disabled'
        return self._get_queue('slow')

    @property
    def backup_queue(self):
        assert self.is_backup, 'Node backup capability disabled'
        return self._get_queue('backup')

    @property
    def image_queue(self):
        # image queue is always available on compute and backup nodes
        return self._get_queue('image')

    @property
    def color(self):
        return '#' + str(self.uuid)[30:]

    @property
    def vendor(self):
        return self._sysinfo.get('Manufacturer', '').replace(' Inc.', '')  # Dell Inc.

    @property
    def model(self):
        sysinfo = self._sysinfo
        product = sysinfo.get('Product', '')

        if sysinfo.get('Manufacturer', None) == 'IBM':
            product = product.split('-')[0].replace('IBM', '')

        return product.replace('Server', '').strip()

    def worker(self, queue):
        return self._get_queue(queue).replace('.', '@', 1)

    @property
    def _system_version_key(self):
        return 'node:%s:system-version' % self.uuid

    @property
    def system_version(self):
        from que.utils import worker_command

        version = cache.get(self._system_version_key)

        if not version:
            worker = self.worker('fast')
            version = worker_command('system_version', worker, timeout=0.5) or ''

            if version:
                cache.set(self._system_version_key, version)

        return version

    @system_version.deleter
    def system_version(self):
        cache.delete(self._system_version_key)

    def has_related_tasks(self):
        """Return True if at least one of node related objects (Vm, Image, NodeStorage) has pending tasks"""
        from vms.models.image import Image, ImageVm  # circular imports

        for vm in self.vm_set.all():
            if vm.tasks:
                return True

        for ns in self.nodestorage_set.all():
            if ns.tasks:
                return True

        if self == ImageVm().node:
            for img in Image.objects.all():
                if img.tasks:
                    return True

        return False


class DcNode(_JsonPickleModel):
    """
    Datacenter <-> Node intermediate model.
    """
    RAM_KVM_OVERHEAD_KEY = 'kvm_memory_overhead-dcnode:%s'  # %s = DcNode.id
    PRIORITY = 100

    # Internal API/GUI constants used for automatic attachment of related node storages when attaching a node into a Dc
    NS_ATTACH_NONE = 0
    NS_ATTACH_ALL = 9

    SHARED = 1
    SHARED_LIMIT = 2
    RESERVED = 3
    STRATEGY = (
        (SHARED, _('Shared')),
        (SHARED_LIMIT, _('Shared with limit')),
        (RESERVED, _('Reserved')),
    )

    # Inherited: json
    dc = models.ForeignKey('Dc')
    node = models.ForeignKey('Node')
    priority = models.PositiveIntegerField(_('Priority'), default=PRIORITY,
                                           help_text=_('Higher priority means that the automatic node chooser'
                                                       ' will more likely choose this node.'))
    cpu = models.PositiveIntegerField(_('CPUs'), help_text=_('Total number of CPUs (cores).'))
    ram = models.PositiveIntegerField(_('RAM (MB)'), help_text=_('Total RAM size in MB.'))
    disk = models.PositiveIntegerField(_('Disk pool size (MB)'), help_text=_('Size of the local disk pool.'))
    cpu_free = models.IntegerField(_('Free CPUs'), default=0, editable=False)
    ram_free = models.IntegerField(_('Free RAM (MB)'), default=0, editable=False)
    disk_free = models.IntegerField(_('Free disk pool size (MB)'), default=0, editable=False)
    strategy = models.SmallIntegerField(_('Resource strategy'), choices=STRATEGY, default=SHARED)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Node')
        verbose_name_plural = _('Nodes')

    def __unicode__(self):
        return '%s@%s' % (self.node, self.dc)

    @property
    def web_data(self):
        """Return dict used in html templates"""
        return {
            'hostname': self.node.hostname,
            'strategy': self.strategy,
            'priority': self.priority,
            'cpu': self.cpu,
            'ram': self.ram,
            'disk': self.disk,
        }

    @property
    def ram_kvm_overhead(self):
        return self.json.get('ram_kvm_overhead', 0)

    @ram_kvm_overhead.setter
    def ram_kvm_overhead(self, value):
        self.save_item('ram_kvm_overhead', value, save=False)

    @classmethod
    def choose_node(cls, dc, vm):
        """Choose appropriate node for a new VM"""
        vm_cpu, vm_ram = vm.get_cpu_ram(ram_overhead=True)
        vm_disk = vm.get_disks()
        resources = {'cpu_free__gte': vm_cpu, 'ram_free__gte': vm_ram}

        if vm_disk:  # First find valid and free storages
            storages = []

            for zpool, size in vm_disk.items():
                storages.append(models.Q(zpool=zpool) & models.Q(storage__size_free__gte=size))

            nodes = NodeStorage.objects.filter(dc=dc, zpool__in=vm_disk.keys()).filter(reduce(operator.or_, storages))\
                                       .distinct('node').values_list('node_id', flat=True)
            resources['node_id__in'] = list(nodes)

            if Node.ZPOOL in vm_disk:
                resources['disk_free__gte'] = vm_disk[Node.ZPOOL]

        try:
            dc_node = cls.objects.filter(dc=dc, node__status=Node.ONLINE, node__is_compute=True).filter(**resources)\
                                 .order_by('-priority', 'cpu_free', 'ram_free', 'disk_free')[0]
        except IndexError:
            return None
        else:
            return dc_node.node

    def check_free_resources(self, cpu=None, ram=None, disk=None):
        """Return True if it is possible to allocate resources on this node"""
        if cpu is not None and cpu > self.cpu_free:
            return False

        if ram is not None and ram > self.ram_free:
            return False

        if disk is not None and disk > self.disk_free:
            return False

        return True

    def get_nonreserved_free_resources(self, exclude_this_dc=False):
        """Return sum of non-reserved free resources on this node"""
        s = models.Sum  # First we need to count all reserved resources
        reserved = r = DcNode.objects.filter(node=self.node, strategy=self.RESERVED)
        dc_exclude = None

        if exclude_this_dc:
            dc_exclude = self.dc
            r = r.exclude(dc=self.dc)

        r = r.aggregate(s('cpu'), s('ram'), s('disk'))
        cpu_n, ram_n, disk_n = map(int, self.node.resources)  # And subtract reserved from real node resources
        cpu_f = cpu_n - (r['cpu__sum'] or 0)
        ram_f = ram_n - (r['ram__sum'] or 0)
        disk_f = disk_n - (r['disk__sum'] or 0)
        self._nonreserved_resources = (cpu_f, ram_f, disk_f)
        dcs_exclude = reserved.distinct('dc').values_list('dc', flat=True)

        return self.node.get_free_resources(cpu_f, ram_f, disk_f, dc_exclude=dc_exclude, dcs_exclude=dcs_exclude)

    def update_resources(self, save=False):
        """Update free dc_node resources according to strategy"""
        if save:
            return self.save(update_resources=True)

        node = self.node
        dc = self.dc

        if self.strategy == self.RESERVED:
            # totals = set by user
            # free = totals - DC VM's resources
            self.cpu_free, self.ram_free, self.disk_free = node.get_free_resources(self.cpu, self.ram, self.disk, dc=dc)

        elif self.strategy in (self.SHARED, self.SHARED_LIMIT):
            self.cpu_free, self.ram_free, self.disk_free = self.get_nonreserved_free_resources()

            if self.strategy == self.SHARED:
                # totals = node resources - reserved
                # free = totals - ALL DcNode non-reserved VM's resources - backups - snapshots
                self.cpu, self.ram, self.disk = self._nonreserved_resources
            else:
                # totals = set by user
                # free = (totals - DC VM's resources) ? (totals - reserved - ALL DcNode non-reserved VM's resources)
                cpu_us, ram_us, disk_us = node.get_free_resources(self.cpu, self.ram, self.disk, dc=dc)
                if cpu_us < self.cpu_free:
                    self.cpu_free = cpu_us
                if ram_us < self.ram_free:
                    self.ram_free = ram_us
                if disk_us < self.disk_free:
                    self.disk_free = disk_us

        self.ram_kvm_overhead = node.get_ram_kvm_overhead(dc=dc)

    def save(self, update_resources=True, **kwargs):
        """Update free resources before saving"""
        if update_resources:
            self.update_resources(save=False)

        ret = super(DcNode, self).save(**kwargs)

        return ret

    @classmethod
    def update_all(cls, node):
        """Re-calculate resources on all DcNodes associated with this node"""
        for dc_node in cls.objects.select_related('node', 'dc').filter(node=node):
            dc_node.update_resources(save=True)

    # noinspection PyUnusedLocal
    @staticmethod
    def post_delete(sender, instance, **kwargs):
        """Cleanup storage"""
        instance.dc.nodestorage_set.remove(*NodeStorage.objects.filter(node=instance.node))
