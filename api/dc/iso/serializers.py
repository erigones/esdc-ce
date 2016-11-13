from api.iso.base.serializers import IsoSerializer as _IsoSerializer


class IsoSerializer(_IsoSerializer):
    """
    Read-only version IsoSerializer
    """
    _update_fields_ = ()

    # noinspection PyUnusedLocal
    def detail_dict(self, **kwargs):
        # Add dc into detail dict
        return {'dc': self.request.dc}
