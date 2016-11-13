from api import serializers as s


class NodeVersionSerializer(s.Serializer):
    hostname = s.Field()
    version = s.Field(source='system_version')
