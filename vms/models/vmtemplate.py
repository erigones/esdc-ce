from django.db import models
from django.utils.translation import ugettext_lazy as _

from vms.utils import DefAttrDict, FrozenAttrDict
# noinspection PyProtectedMember
from vms.mixins import _DcMixin
# noinspection PyProtectedMember
from vms.models.base import _VirtModel, _JsonPickleModel, _OSType, _UserTasksModel


class _DefineList(list):
    """
    Wrapper around list of definition objects.
    """
    definition = True
    template = None

    def __init__(self, data, definition, template):
        super(_DefineList, self).__init__(data)
        self.definition = definition
        self.template = template


class _DiskObject(DefAttrDict):
    """
    Simulate _DiskModel object (used by objects vm_define_backup and vm_define_snapshot web GUI list).
    """
    OBJ_DEFAULT = FrozenAttrDict(active=True, disk_id=1, disk_size=0, schedule='(auto)')

    def __init__(self, data, defaults=OBJ_DEFAULT):
        super(_DiskObject, self).__init__(data, defaults=defaults)

    @property
    def array_disk_id(self):
        return self.disk_id


class _SnapshotDefineObject(_DiskObject):
    """
    Snapshot define object used in vm_define web GUI list.
    """
    def __init__(self, data):
        if 'name' in data:
            data['snapdef'] = data['name']
        if 'snapdef' in data:
            data['name'] = data['snapdef']
        super(_SnapshotDefineObject, self).__init__(data)


class _BackupDefineObject(_DiskObject):
    """
    Backup define object used in vm_define web GUI list.
    """
    def __init__(self, data):
        from vms.models.backup import BackupDefine  # circular imports
        self.BACKUP_DEFINE_TYPE = dict(BackupDefine.TYPE)
        defaults = self.OBJ_DEFAULT
        defaults['type'] = BackupDefine.DATASET

        if 'name' in data:
            data['bkpdef'] = data['name']
        if 'bkpdef' in data:
            data['name'] = data['bkpdef']
        super(_BackupDefineObject, self).__init__(data, defaults=defaults)

    @property
    def get_type_display(self):
        return self.BACKUP_DEFINE_TYPE.get(self.type)


class VmTemplate(_VirtModel, _JsonPickleModel, _OSType, _DcMixin, _UserTasksModel):
    """
    VM Template. The json dict is copied to new VMs.
    """
    DEFINE_KEYS = ('vm_define', 'vm_define_disk', 'vm_define_nic', 'vm_define_snapshot', 'vm_define_backup')

    ACCESS = (
        (_VirtModel.PUBLIC, _('Public')),
        (_VirtModel.PRIVATE, _('Private')),
        (_VirtModel.DELETED, _('Deleted')),
    )

    new = False
    _pk_key = 'vmtemplate_id'  # _UserTasksModel

    # Inherited: name, alias, owner, desc, access, created, changed, json, dc, dc_bound
    ostype = models.SmallIntegerField(_('Guest OS type'), choices=_OSType.OSTYPE, null=True, blank=True)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Template')
        verbose_name_plural = _('Templates')
        unique_together = (('alias', 'owner'),)

    def __init__(self, *args, **kwargs):
        super(VmTemplate, self).__init__(*args, **kwargs)
        if not self.pk:
            self.new = True

    def save(self, *args, **kwargs):
        """Save template and update json dict with template name"""
        _json = self.json

        if not isinstance(_json, dict) or not _json:
            _json = {}
        if 'internal_metadata' not in _json or not isinstance(_json['internal_metadata'], dict):
            _json['internal_metadata'] = {}

        _json['internal_metadata']['template'] = self.name
        self.json = _json

        return super(VmTemplate, self).save(*args, **kwargs)

    @property
    def web_data(self):
        """Return dict used in server web templates"""
        data = self.vm_define
        data['ostype'] = self.ostype

        return data

    @property
    def web_data_admin(self):
        """Return dict used in admin/DC web templates"""
        return {
            'name': self.name,
            'alias': self.alias,
            'access': self.access,
            'owner': self.owner.username,
            'ostype': self.ostype,
            'desc': self.desc,
            'dc_bound': self.dc_bound_bool,
        }

    def get_json(self):
        """Return self.json without vm_define* stuff"""
        _json = self.json

        for key in self.DEFINE_KEYS:
            try:
                del _json[key]
            except KeyError:
                pass

        return _json

    def _get_list(self, key, pos=None):
        """Return list or one list item from json.key"""
        data = self.json.get(key, [])

        if pos is None:
            return _DefineList(data, key, self)

        try:
            return data[pos]
        except IndexError:
            return {}

    def _save_item(self, key, value):
        if value:
            self.save_item(key, value, save=False)
        else:
            self.delete_item(key, save=False)

    def get_vm_define_disk(self, disk_id=None):
        """Return data suitable for api.vm.define.vm_define_disk"""
        return self._get_list('vm_define_disk', pos=disk_id)

    def get_vm_define_nic(self, nic_id=None):
        """Return data suitable for api.vm.define.vm_define_nic"""
        return self._get_list('vm_define_nic', pos=nic_id)

    @property
    def internal_metadata(self):
        return self.json.get('internal_metadata', {})

    @property
    def vm_define(self):
        """Return data suitable for api.vm.define.vm_define"""
        return self.json.get('vm_define', {})

    @vm_define.setter
    def vm_define(self, value):
        self._save_item('vm_define', value)

    @property
    def vm_define_nic(self):
        """Return data suitable for api.vm.define.vm_define_nic"""
        return self.get_vm_define_nic()

    @vm_define_nic.setter
    def vm_define_nic(self, value):
        self._save_item('vm_define_nic', value)

    @property
    def vm_define_disk(self):
        """Return data suitable for api.vm.define.vm_define_disk"""
        return self.get_vm_define_disk()

    @vm_define_disk.setter
    def vm_define_disk(self, value):
        self._save_item('vm_define_disk', value)

    @property
    def vm_define_disk_0(self):
        return self.get_vm_define_disk(disk_id=0)

    @property
    def vm_define_snapshot(self):
        """Return data suitable for api.vm.snapshot.vm_define_snapshot"""
        return self._get_list('vm_define_snapshot')

    @vm_define_snapshot.setter
    def vm_define_snapshot(self, value):
        self._save_item('vm_define_snapshot', value)

    @property
    def vm_define_backup(self):
        """Return data suitable for api.vm.backup.vm_define_backup"""
        return self._get_list('vm_define_backup')

    @vm_define_backup.setter
    def vm_define_backup(self, value):
        self._save_item('vm_define_backup', value)

    @property
    def vm_define_snapshot_web_data(self):
        """Return data suitable for web GUI display in server snapshot define view"""
        array = self.vm_define_snapshot
        array[:] = [_SnapshotDefineObject(data) for data in array]

        return array

    @property
    def vm_define_backup_web_data(self):
        """Return data suitable for web GUI display in server backup define view"""
        array = self.vm_define_backup
        array[:] = [_BackupDefineObject(data) for data in array]

        return array
