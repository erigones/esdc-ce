from uuid import uuid4
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.core.cache import cache
from frozendict import frozendict

from vms.utils import PickleDict, FrozenAttrDict
# noinspection PyProtectedMember
from vms.mixins import _DcMixin
# noinspection PyProtectedMember
from vms.models.base import _VirtModel, _JsonPickleModel, _OSType, _UserTasksModel
from vms.models.vm import Vm
from vms.models.snapshot import Snapshot


class Image(_VirtModel, _JsonPickleModel, _OSType, _DcMixin, _UserTasksModel):
    """
    VM Image. The json dict will be a imgadm manifest.
    """
    _MANIFEST_TEMPLATE = frozendict({
        u'v': 2,
        u'owner': u'00000000-0000-0000-0000-000000000000',
        u'state': u'active',
        u'disabled': False,
        u'public': False,
    })

    OSTYPE2OS = frozendict({
        _OSType.LINUX: u'linux',
        _OSType.BSD: u'bsd',
        _OSType.WINDOWS: u'windows',
        _OSType.SUNOS: u'illumos',
        _OSType.SUNOS_ZONE: u'smartos',
        _OSType.LINUX_ZONE: u'other',
    })

    # Used in add server and in payments during define_vm
    CUSTOM = frozendict({
        _OSType.LINUX: FrozenAttrDict({
            'name': 'custom_linux',
            'desc': 'Custom Linux',
            'note': _('Install your favourite OS from ISO image.'),
            'access': _VirtModel.PUBLIC,
            'deploy': False,
            'resize': False,
            'ostype': _OSType.LINUX,
        }),
        _OSType.BSD: FrozenAttrDict({
            'name': 'custom_bsd',
            'desc': 'Custom BSD',
            'note': _('Install your favourite OS from ISO image.'),
            'access': _VirtModel.PUBLIC,
            'deploy': False,
            'resize': False,
            'ostype': _OSType.BSD,
        }),
        _OSType.SUNOS: FrozenAttrDict({
            'name': 'custom_sunos',
            'desc': 'Custom SunOS',
            'note': _('Install your favourite OS from ISO image.'),
            'access': _VirtModel.PRIVATE,
            'deploy': False,
            'resize': False,
            'ostype': _OSType.SUNOS,
        }),
        _OSType.WINDOWS: FrozenAttrDict({
            'name': 'custom_windows',
            'desc': 'Custom Windows',
            'note': _('Install your favourite OS from ISO image.'),
            'access': _VirtModel.PRIVATE,
            'deploy': False,
            'resize': False,
            'ostype': _OSType.WINDOWS,
        }),
    })

    ACCESS = (
        (_VirtModel.PUBLIC, _('Public')),
        (_VirtModel.PRIVATE, _('Private')),
        (_VirtModel.DELETED, _('Deleted')),
    )

    OK = 1
    PENDING = 2
    STATUS = (
        (OK, _('ok')),
        (PENDING, _('pending')),
    )

    READY = 1
    IMPORTING = 2
    DELETING = 3
    NS_STATUS = (
        (READY, _('ready')),
        (IMPORTING, _('importing')),
        (DELETING, _('deleting')),
    )

    TAGS_KEY = u'erigones'
    DEFAULT_SIZE = 1024  # MB
    # Used in NodeStorage.size_images
    IMAGE_SIZE_TOTAL_KEY = 'image-size-total:%s'  # %s = zpool.id (NodeStorage)

    new = False
    _pk_key = 'image_uuid'  # _UserTasksModel
    _src_vm = None  # Cached source VM object
    _src_snap = None  # Cache source Snapshot object

    # Inherited: name, alias, owner, desc, access, created, changed, json, dc, dc_bound
    uuid = models.CharField(_('UUID'), max_length=36, primary_key=True)
    version = models.CharField(_('Image version'), max_length=16)
    size = models.IntegerField(_('Image size (MB)'),
                               help_text=_('Exact same value as in imgadm manifest attribute image_size.'))
    ostype = models.SmallIntegerField(_('Guest OS type'), choices=_OSType.OSTYPE)
    deploy = models.BooleanField(_('Deploy required?'), default=False)
    resize = models.BooleanField(_('Resizable?'), default=False)
    status = models.SmallIntegerField(_('Status'), choices=STATUS)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Image')
        verbose_name_plural = _('Images')
        # xenol
        unique_together = (('alias', 'owner', 'version'),)

    def __init__(self, *args, **kwargs):
        super(Image, self).__init__(*args, **kwargs)
        if not self.uuid:
            self.new = True
            self.uuid = str(uuid4())

    @classmethod
    def ostype_to_os(cls, ostype):
        """Convert our ostype to IMG API os"""
        return cls.OSTYPE2OS[ostype]

    @classmethod
    def os_to_ostype(cls, manifest):
        """Convert IMG API os to our ostype"""
        if manifest['type'] == 'zone-dataset':
            return Image.SUNOS_ZONE
        elif manifest['type'] == 'lx-dataset':
            return Image.LINUX_ZONE
        else:  # zvol - KVM
            os = manifest['os'].lower()

            if os == cls.OSTYPE2OS[_OSType.SUNOS_ZONE]:  # smartos
                return _OSType.SUNOS

            os2ostype = {v: k for k, v in cls.OSTYPE2OS.items() if k in cls.KVM}

            return os2ostype.get(manifest['os'], Image.LINUX)  # fallback for 'other' is Linux

    @property
    def note(self):
        """Used in billing version of add server view"""
        if self.access == self.DISABLED:
            return _('Coming Soon')
        else:
            return ''

    @property
    def alias_version(self):
        """Alias including version - used in GUI"""
        return '%s (%s)' % (self.alias, self.version)

    @property
    def tags(self):
        return self.json.get('tags', [])

    @tags.setter
    def tags(self, value):
        self.save_item('tags', value, save=False)

    @property
    def tag_list(self):
        if not self.tags:
            return ''

        return ','.join(map(unicode, sorted(self.tags)))

    @property
    def manifest(self):
        return PickleDict(self.json.get('manifest', {}))

    @manifest.setter
    def manifest(self, value):
        self.save_item('manifest', value, save=False)

    @property
    def manifest_active(self):
        return PickleDict(self.json.get('manifest_active', {}))

    @manifest_active.setter
    def manifest_active(self, value):
        self.save_item('manifest_active', value, save=False)

    @property
    def requirements(self):
        return self.manifest_active.get('requirements', {})

    @property
    def min_platform(self):
        return self.requirements.get('min_platform', {}).get(settings.VMS_SDC_VERSION, None)

    @property
    def max_platform(self):
        return self.requirements.get('max_platform', {}).get(settings.VMS_SDC_VERSION, None)

    def build_manifest(self):
        """Create new manifest from DB fields"""
        manifest = dict(self._MANIFEST_TEMPLATE)
        manifest.update(self.manifest)
        manifest.update({
            u'uuid': self.uuid,
            u'name': self.alias,
            u'version': self.version,
            u'state': u'active',
            u'disabled': (self.access in (self.DISABLED, self.INTERNAL)),
            u'public': (self.access == self.PUBLIC),
            u'os': self.ostype_to_os(self.ostype),
            u'description': self.desc,
            u'image_size': self.size,
        })

        if u'tags' not in manifest:
            manifest[u'tags'] = {}

        manifest[u'tags'].update({
            self.TAGS_KEY: self.tags,
            'resize': self.resize,
            'deploy': self.deploy,
            'internal': self.access == self.INTERNAL,
        })

        if self.ostype in self.ZONE:
            for i in ('image_size', 'nic_driver', 'disk_driver', 'cpu_type'):
                try:
                    del manifest[i]
                except KeyError:
                    pass

            if self.ostype == self.SUNOS_ZONE:
                img_type = u'zone-dataset'
            elif self.ostype == self.LINUX_ZONE:
                img_type = u'lx-dataset'
            else:
                img_type = u'other'
        else:
            manifest[u'image_size'] = self.size
            manifest[u'cpu_type'] = manifest.get('cpu_type', u'qemu64')
            # TODO: nic_driver, disk_driver
            img_type = u'zvol'

        if manifest.get('type', None) != 'other':
            manifest[u'type'] = img_type

        if u'published_at' not in manifest:
            manifest[u'published_at'] = timezone.now().isoformat()

        return manifest

    def default_apiview(self):
        """Return dict with attributes which are always available in apiview"""
        return {
            'status': self.status,
            'status_display': self.get_status_display(),
        }

    @property
    def web_data(self):
        """Return dict used in server web templates"""
        return {'size': self.size}

    @property
    def web_data_admin(self):
        """Return dict used in admin/DC web templates"""
        return {
            'name': self.name,
            'alias': self.alias,
            'version': self.version,
            'access': self.access,
            'owner': self.owner.username,
            'ostype': self.ostype,
            'desc': self.desc,
            'dc_bound': self.dc_bound_bool,
            'resize': self.resize,
            'deploy': self.deploy,
            'tags': self.tag_list,
        }

    def save_status(self, new_status=None, **kwargs):
        """Just update the status field (and other related fields)"""
        if new_status is not None:
            self.status = new_status

        return self.save(update_fields=('status',), **kwargs)

    def is_ok(self):
        return self.status == self.OK

    def is_used_by_vms(self, dc=None, zpool=None):
        if dc:
            vms = dc.vm_set.all()
        else:
            vms = Vm.objects.filter(dc__in=self.dc.all())

        for vm in vms:
            if self.uuid in vm.get_image_uuids(zpool=zpool):
                return True

        return False

    def _get_ns_key(self, ns):
        return 'img:%s:ns:%s' % (self.uuid, ns.id)

    def get_block_key(self, ns):
        return '%s:%s:%s' % (cache.key_prefix, cache.version, self._get_ns_key(ns))

    def set_ns_status(self, ns, status):
        cache.set(self._get_ns_key(ns), status, 3600 * 24)

    def del_ns_status(self, ns):
        cache.delete(self._get_ns_key(ns))

    def get_ns_status(self, ns):
        status = cache.get(self._get_ns_key(ns))

        if not status:
            return self.READY

        return status

    def get_ns_status_display(self, ns):
        return dict(self.NS_STATUS).get(self.get_ns_status(ns))

    @property
    def src_vm_uuid(self):
        """Source VM"""
        return self.json.get('vm_uuid', None)

    @src_vm_uuid.setter
    def src_vm_uuid(self, value):
        self.save_item('vm_uuid', value, save=False)

    @property
    def src_snap_id(self):
        """Source snapshot"""
        return self.json.get('snap_id', None)

    @src_snap_id.setter
    def src_snap_id(self, value):
        self.save_item('snap_id', value, save=False)

    @property
    def src_vm(self):
        if self._src_vm is None and self.src_vm_uuid:
            try:
                self._src_vm = Vm.objects.get(uuid=self.src_vm_uuid)
            except Vm.DoesNotExist:
                self.src_vm_uuid = None
                self.save(update_fields=('enc_json',))

        return self._src_vm

    @src_vm.setter
    def src_vm(self, vm):
        self.src_vm_uuid = vm.uuid
        self._src_vm = vm

    @property
    def src_snap(self):
        if self._src_snap is None and self.src_snap_id:
            try:
                self._src_snap = Snapshot.objects.get(id=self.src_snap_id)
            except Snapshot.DoesNotExist:
                self.src_snap_id = None
                self.save(update_fields=('enc_json',))

        return self._src_snap

    @src_snap.setter
    def src_snap(self, snap):
        self.src_snap_id = snap.id
        self._src_snap = snap

    def tasks_add(self, task_id, apiview, msg='', **additional_apiview):
        """Add task to pending tasks dict in cache."""
        info = self._create_task_info(self.pk, apiview, msg, additional_apiview=additional_apiview)

        if apiview.get('view') == 'image_snapshot':
            vm = self.src_vm

            if vm.owner_id == self.owner_id:
                # noinspection PyProtectedMember
                info[vm._pk_key] = vm.pk  # Share the same UserTask
            else:
                info2 = info.copy()
                # noinspection PyProtectedMember
                info2[vm._pk_key] = vm.pk
                self._add_task(vm.owner_id, task_id, info2)  # Add another UserTask entry

        return self._add_task(self.owner_id, task_id, info)

    def tasks_del(self, task_id, **additional_apiview):
        """Delete task from pending tasks dict in cache."""
        apiview = super(Image, self).tasks_del(task_id, **additional_apiview)

        if apiview.get('view') == 'image_snapshot':
            vm = self.src_vm

            if vm.owner_id != self.owner_id:
                self._pop_task(vm.owner_id, task_id)

        return apiview


class ImageVm(object):
    """
    Image server.
    """
    _cache_key = 'image:vm'
    vm = None

    def __init__(self):
        # Initialize image server VM
        self.vm = self._get_vm()

    def _get_vm(self):
        from vms.models import Vm

        vm = cache.get(self._cache_key)

        if not vm:
            vm = Vm.objects.select_related('node').get(uuid=settings.VMS_IMAGE_VM)
            cache.set(self._cache_key, vm)

        return vm

    @classmethod
    def reset(cls):
        cache.delete(cls._cache_key)

    @property
    def node(self):
        return self.vm.node

    @property
    def node_status(self):
        node = self.node
        return node.__class__.objects.only('status').get(pk=node.pk).status

    @property
    def vm_status(self):
        return self.vm.__class__.objects.only('status').get(pk=self.vm.pk).status

    @property
    def datasets_dir(self):
        return '/%s/root/datasets' % self.vm.json_active['zfs_filesystem']

    @property
    def sources(self):
        try:
            src = ['http://%s' % self.vm.ips[0]]
        except IndexError:
            src = []

        src.extend(settings.VMS_IMAGE_SOURCES)

        return src

    def sources_update(self, imgadm_sources):
        if self.vm:
            wanted = set(self.sources)
        else:
            wanted = set(settings.VMS_IMAGE_SOURCES)

        current = set(imgadm_sources)
        add = wanted - current
        rem = current - wanted

        if add or rem:
            return add, rem

        return None
