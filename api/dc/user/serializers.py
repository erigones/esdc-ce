from api.accounts.user.base.serializers import UserSerializer as _UserSerializer


class UserSerializer(_UserSerializer):
    """
    Read-only version UserSerializer.
    """
    _update_fields_ = ()

    def detail_dict(self, **kwargs):
        # Add dc into detail dict
        return {'dc': self.request.dc}
