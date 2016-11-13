from api.image.base.serializers import ImageSerializer as _ImageSerializer


class ImageSerializer(_ImageSerializer):
    """
    Read-only version of ImageSerializer
    """
    _update_fields_ = ()

    def detail_dict(self, **kwargs):
        # Add dc into detail dict
        return {'dc': self.request.dc}
