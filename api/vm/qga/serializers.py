from api import serializers as s


class VmQGASerializer(s.Serializer):
    """
    Validate QGA command parameters.
    """
    params = s.ArrayField(max_items=1)

    def __init__(self, request, command, *args, **kwargs):
        self.request = request
        self.command = command
        super(VmQGASerializer, self).__init__(*args, **kwargs)

    def get_full_command(self):
        assert self.data is not None  # Make sure that the serializer was validated

        return [self.command] + self.object['params']

    def detail_dict(self, **kwargs):
        res = super(VmQGASerializer, self).detail_dict(**kwargs)
        res['command'] = self.command

        return res
