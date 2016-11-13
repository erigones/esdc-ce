from django.utils.translation import ugettext_lazy as _

from api import serializers as s
from api.validators import validate_owner, validate_alias
from api.vm.utils import get_owners
from vms.models import NodeStorage, Storage
from gui.models import User


class NodeStorageSerializer(s.InstanceSerializer):
    """
    vms.models.NodeStorage
    """
    error_negative_resources = s.ErrorList([_('Value is too low because of existing virtual machines.')])

    _model_ = NodeStorage
    _default_fields_ = ('alias', 'owner', 'size_coef', 'zpool')

    node = s.Field(source='node.hostname')
    zpool = s.ChoiceField(source='zpool')
    alias = s.SafeCharField(source='storage.alias', max_length=32)
    owner = s.SlugRelatedField(source='storage.owner', slug_field='username', queryset=User.objects, required=False)
    access = s.IntegerChoiceField(source='storage.access', choices=Storage.ACCESS, default=Storage.PRIVATE)
    type = s.IntegerChoiceField(source='storage.type', choices=Storage.TYPE, default=Storage.LOCAL)
    size = s.IntegerField(source='storage.size_total', read_only=True)
    size_coef = s.DecimalField(source='storage.size_coef', min_value=0, max_digits=4, decimal_places=2)
    size_free = s.IntegerField(source='storage.size_free', read_only=True)
    created = s.DateTimeField(source='storage.created', read_only=True, required=False)
    desc = s.SafeCharField(source='storage.desc', max_length=128, required=False)

    def __init__(self, request, instance, *args, **kwargs):
        self._update_fields_ = ['alias', 'owner', 'access', 'desc', 'type', 'size_coef']
        super(NodeStorageSerializer, self).__init__(request, instance, *args, **kwargs)

        if not kwargs.get('many', False):
            self._size_coef = instance.storage.size_coef
            self.fields['owner'].queryset = get_owners(request)

            if request.method == 'POST':
                self.fields['zpool'].choices = [(i, i) for i in instance.node.zpools.keys()]
                self._update_fields_.append('zpool')
            else:
                self.fields['zpool'].read_only = True

    def validate_owner(self, attrs, source):
        """Cannot change owner while pending tasks exist"""
        validate_owner(self.object, attrs.get(source, None), _('Storage'))

        return attrs

    def validate_alias(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            validate_alias(self.object, value, field_comparison='storage__alias__iexact')

        return attrs

    def validate(self, attrs):
        # Default owner is request.user, but setting this in __init__ does not work
        if 'storage.owner' in attrs and attrs['storage.owner'] is None:
            if self.object.pk:
                del attrs['storage.owner']
            else:
                attrs['storage.owner'] = self.request.user

        return attrs

    @property
    def update_storage_resources(self):
        """True if size_coef changed"""
        return not(self.object.storage.size_coef == self._size_coef)


class ExtendedNodeStorageSerializer(NodeStorageSerializer):
    size_vms = s.IntegerField(read_only=True)
    size_snapshots = s.IntegerField(read_only=True)
    size_rep_snapshots = s.IntegerField(read_only=True)
    size_backups = s.IntegerField(read_only=True)
    # size_images = s.IntegerField(read_only=True)  # TODO: fix size_images implementation and enable
    snapshots = s.IntegerField(read_only=True, source='snapshot_count')
    backups = s.IntegerField(read_only=True, source='backup_count')
    images = s.IntegerField(read_only=True, source='image_count')
    dcs = s.DcsField()
    vms = s.ArrayField(read_only=True)
