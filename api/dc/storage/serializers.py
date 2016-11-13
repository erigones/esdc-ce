from api import serializers as s
from vms.models import NodeStorage


class DcNodeStorageSerializer(s.InstanceSerializer):
    """
    vms.models.NodeStorage
    """
    _model_ = NodeStorage

    node = s.Field(source='node.hostname')
    zpool = s.Field()
    alias = s.Field(source='storage.alias')
    owner = s.Field(source='storage.owner.username')
    access = s.IntegerField(source='storage.access', read_only=True)
    type = s.IntegerField(source='storage.type', read_only=True)
    size = s.IntegerField(read_only=True)  # storage.size_total or dc_node.disk if local storage
    size_free = s.IntegerField(read_only=True)  # storage.size_free or dc_node.disk_free if local storage
    desc = s.Field(source='storage.desc')

    def detail_dict(self, **kwargs):
        # Add dc into detail dict
        return {'dc': self.request.dc}


class ExtendedDcNodeStorageSerializer(DcNodeStorageSerializer):
    size_vms = s.IntegerField(read_only=True, source='size_dc_vms')
    size_snapshots = s.IntegerField(read_only=True, source='size_dc_snapshots')
    size_backups = s.IntegerField(read_only=True, source='size_dc_backups')
