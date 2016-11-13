from api.dns.domain.serializers import DomainSerializer as _DomainSerializer


class DomainSerializer(_DomainSerializer):
    """
    Read-only version DomainSerializer
    """
    _update_fields_ = ()

    # noinspection PyUnusedLocal
    def detail_dict(self, **kwargs):
        # Add dc into detail dict
        return {'dc': self.request.dc}
