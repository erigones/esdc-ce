from api.network.base.serializers import NetworkSerializer as _NetworkSerializer


class NetworkSerializer(_NetworkSerializer):
    """
    Read-only version of NetworkSerializer
    """
    _update_fields_ = ()

    # noinspection PyUnusedLocal
    def detail_dict(self, **kwargs):
        # Add dc into detail dict
        return {'dc': self.request.dc}
