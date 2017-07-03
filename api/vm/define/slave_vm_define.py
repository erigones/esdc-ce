from django.utils.translation import ugettext_lazy as _

from api.serializers import APIValidationError
from vms.models import NodeStorage, Image


class SlaveVmDefine(object):
    """
    A Slave VM is a copy of a VM used to take up place in DB.
    It is used during migration and as a representation of a real replicated VM.
    This helper is used for validating and updating slave VM resources before it is saved in DB.
    """
    def __init__(self, slave_vm):
        self.slave_vm = slave_vm
        self.vm = slave_vm.vm
        self._nss = {}

    @staticmethod
    def get_zpool(disk):
        """Return zpool part from zfs_filesystem attribute"""
        try:
            return disk['zfs_filesystem'].split('/')[0]
        except (KeyError, IndexError):
            raise APIValidationError('Invalid disk configuration.')

    @staticmethod
    def _change_zpool(dataset, zpool):
        """Switch zpool on dataset"""
        fs = dataset.split('/')
        fs[0] = zpool.strip()
        return '/'.join(fs)

    @classmethod
    def change_zpool(cls, disk, zpool):
        """Switch zpool in zfs_filesystem attribute"""
        try:
            dataset = disk['zfs_filesystem']
        except KeyError:
            raise APIValidationError('Invalid disk configuration.')
        else:
            return cls._change_zpool(dataset, zpool)

    def _change_zfs_filesystem(self, node_storage, disk_or_json, save_same_zpool=True):
        """Return changed zfs_filesystem and save affected node storage"""
        new_zpool = node_storage.zpool
        old_zpool = self.get_zpool(disk_or_json)
        new_fs = self.change_zpool(disk_or_json, new_zpool)

        if old_zpool == new_zpool:
            new_zpool = None

            if save_same_zpool:
                self._nss[old_zpool] = node_storage

        else:
            self._nss[new_zpool] = node_storage

        return new_fs, new_zpool

    def validate_zpool(self, zpool):
        """Return NodeStorage object or raise ValidationError"""
        try:
            return self.vm.node.get_node_storage(self.vm.dc, zpool)
        except NodeStorage.DoesNotExist:
            msg = _('Storage with zpool=%(zpool)s does not exist on target node.')
            raise APIValidationError(msg % {'zpool': zpool})

    def save_root_zpool(self, root_zpool, save_same_zpool=True):
        """Validate and save new root zpool"""
        vm = self.vm
        json = vm.json

        if not root_zpool and save_same_zpool:
            root_zpool = self.get_zpool(json)

        if not root_zpool:
            return None

        root_ns = self.validate_zpool(root_zpool)
        json['zfs_filesystem'], new_root_zpool = self._change_zfs_filesystem(root_ns, json, save_same_zpool)

        if new_root_zpool:  # pool changed
            json['zpool'] = new_root_zpool

            if not vm.is_kvm():
                datasets = json.get('datasets', ())

                # changing delegated datasets
                for i, dataset in enumerate(datasets):
                    json['datasets'][i] = self._change_zpool(dataset, new_root_zpool)

            vm.json = json

        return new_root_zpool

    def save_disk_zpools(self, disk_zpools, save_same_zpool=True):
        """Validate and save new zpools for KVM disks"""
        vm = self.vm
        json = vm.json
        disks = vm.json_get_disks()

        for i, disk in enumerate(disks, start=1):
            if not save_same_zpool and i not in disk_zpools:
                del disks[i - 1]  # Local migration and disk pool has not changed
                continue

            zpool = disk_zpools.get(i, self.get_zpool(disk))
            ns = self.validate_zpool(zpool)
            disks[i - 1]['zfs_filesystem'], new_disk_zpool = self._change_zfs_filesystem(ns, disk, save_same_zpool)

            if new_disk_zpool:
                disks[i - 1]['zpool'] = zpool
            else:
                disk_zpools.pop(i, None)
                if not save_same_zpool:
                    del disks[i - 1]

        # Save disks into json
        json['disks'] = disks
        vm.json = json

        return disk_zpools

    def validate_node_resources(self, ignore_cpu_ram=False, ignore_disk=False):
        """Validate dc_node resources"""
        vm = self.vm
        node = vm.node
        dc_node = node.get_dc_node(vm.dc)
        vm_resources = vm.get_cpu_ram_disk(zpool=node.zpool, ram_overhead=True, ignore_cpu_ram=ignore_cpu_ram,
                                           ignore_disk=ignore_disk)

        if not dc_node.check_free_resources(*vm_resources):
            raise APIValidationError(_('Not enough free resources on target node.'))

    def validate_storage_resources(self):
        """Validate node storage resources"""
        for zpool, size in self.vm.get_disks().items():
            ns = self._nss[zpool]

            if not ns.check_free_space(size):
                raise APIValidationError(_('Not enough free disk space on target storage with zpool=%s.') % zpool)

    def check_required_images(self):
        """Check if images are available on new node storages"""
        for disk in self.vm.json_get_disks():
            if 'image_uuid' in disk:
                ns = self._nss[disk['zpool']]

                if not ns.images.filter(uuid=disk['image_uuid']).exists():
                    return ns, Image.objects.get(uuid=disk['image_uuid'])

        return None

    def save(self, **kwargs):
        """Save slave VM and force update of DC resource counters"""
        self.slave_vm.save(update_node_resources=True, update_storage_resources=self._nss.values(), **kwargs)
