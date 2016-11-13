from api.accounts.group.serializers import GroupSerializer as _GroupSerializer


class GroupSerializer(_GroupSerializer):
    """
    Read-only version GroupSerializer.
    """
    _update_fields_ = ()

    # noinspection PyUnusedLocal
    def detail_dict(self, **kwargs):
        # Add dc into detail dict
        return {'dc': self.request.dc}
