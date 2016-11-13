from api.fields import ArrayField
from api.dc.image.serializers import ImageSerializer


class NodeImageSerializer(ImageSerializer):
    """
    Read-only version of ImageSerializer
    """
    _update_fields_ = ()

    def detail_dict(self, **kwargs):
        return {'image': self.object.name}


class ExtendedNodeImageSerializer(NodeImageSerializer):
    vms = ArrayField(read_only=True)
