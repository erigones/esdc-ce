from api import serializers as s


class HostgroupSerializer(s.Serializer):
    name = s.SafeCharField(max_length=40)  # The name in Zabbix will be prefixed with DC name

    def __init__(self, request, *args, **kwargs):
        super(HostgroupSerializer, self).__init__(*args, **kwargs)
        self.request = request
