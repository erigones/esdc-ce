from api import serializers as s
from gui.models import Permission


class PermissionSerializer(s.InstanceSerializer):
    """
    gui.models.permission
    """
    _model_ = Permission
    _default_fields_ = ('name', 'alias')

    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=80)
    alias = s.SafeCharField(max_length=80)
