from copy import deepcopy

from django.utils.translation import ugettext_lazy as _
from django.utils.six import iteritems

from api import serializers as s
from api.validators import validate_alias
from api.vm.utils import get_owners
from api.vm.define.serializers import VmDefineSerializer, KVmDefineDiskSerializer, VmDefineNicSerializer
from api.vm.snapshot.serializers import SnapshotDefineSerializer
from api.vm.backup.serializers import BackupDefineSerializer
from gui.models import User
from vms.models import VmTemplate


def create_dummy_serializer(serializer_cls, skip_fields=(), required_fields=()):
    """Convert existing serializer class into serializer that can be used as a serializer field.
    The resulting serializer is missing the original validators and field required attribute

    @type serializer_cls: api.serializers.Serializer
    """
    class Serializer(s.Serializer):
        pass

    # noinspection PyUnresolvedReferences
    for name, field in iteritems(serializer_cls.base_fields):
        if name in skip_fields or field.read_only:
            continue

        if isinstance(field, s.RelatedField):
            new_field = s.CharField()
        else:
            new_field = deepcopy(field)  # Do not touch the original field

        if name in required_fields:
            new_field.required = True
        else:
            new_field.required = False

        # noinspection PyUnresolvedReferences
        Serializer.base_fields[name] = new_field

    return Serializer


def validate_dummy_serializer(serializer, value):
    ser = serializer(data=value)
    ser.is_valid()

    for i in ser.init_data:
        if i not in ser.fields:
            # noinspection PyProtectedMember
            ser._errors[i] = s.ErrorList([_('Invalid field.')])

    if ser.errors:
        raise s.NestedValidationError(ser.errors)


class _DefineField(s.DictField):
    _serializer = None

    def validate(self, value):
        validate_dummy_serializer(self._serializer, value)


class VmDefineField(_DefineField):
    _serializer = create_dummy_serializer(VmDefineSerializer)


class _DefineArrayField(s.DictArrayField):
    _serializer = None

    def validate(self, value):
        super(_DefineArrayField, self).validate(value)

        for i in value:
            validate_dummy_serializer(self._serializer, i)


class VmDefineDiskField(_DefineArrayField):
    _serializer = create_dummy_serializer(KVmDefineDiskSerializer)


class VmDefineNicField(_DefineArrayField):
    _serializer = create_dummy_serializer(VmDefineNicSerializer)


class VmDefineSnapshotField(_DefineArrayField):
    _serializer = create_dummy_serializer(SnapshotDefineSerializer, required_fields=('name',))


class VmDefineBackupField(_DefineArrayField):
    _serializer = create_dummy_serializer(BackupDefineSerializer, required_fields=('name',))


class TemplateSerializer(s.ConditionalDCBoundSerializer):
    """
    vms.models.Template
    """
    _model_ = VmTemplate
    _update_fields_ = ('alias', 'owner', 'access', 'desc', 'ostype', 'dc_bound', 'vm_define',
                       'vm_define_disk', 'vm_define_nic', 'vm_define_snapshot', 'vm_define_backup')
    _default_fields_ = ('name', 'alias', 'owner')
    _null_fields_ = frozenset({'ostype', 'vm_define', 'vm_define_disk',
                               'vm_define_nic', 'vm_define_snapshot', 'vm_define_backup'})

    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=32)
    alias = s.SafeCharField(max_length=32)
    owner = s.SlugRelatedField(slug_field='username', queryset=User.objects, required=False)
    access = s.IntegerChoiceField(choices=VmTemplate.ACCESS, default=VmTemplate.PRIVATE)
    desc = s.SafeCharField(max_length=128, required=False)
    ostype = s.IntegerChoiceField(choices=VmTemplate.OSTYPE, required=False, default=None)
    vm_define = VmDefineField(default={}, required=False)
    vm_define_disk = VmDefineDiskField(default=[], required=False, max_items=2)
    vm_define_nic = VmDefineNicField(default=[], required=False, max_items=4)
    vm_define_snapshot = VmDefineSnapshotField(default=[], required=False, max_items=16)
    vm_define_backup = VmDefineBackupField(default=[], required=False, max_items=16)
    created = s.DateTimeField(read_only=True, required=False)

    def __init__(self, request, tmp, *args, **kwargs):
        super(TemplateSerializer, self).__init__(request, tmp, *args, **kwargs)
        if not kwargs.get('many', False):
            self._dc_bound = tmp.dc_bound
            self.fields['owner'].queryset = get_owners(request, all=True)

    def _normalize(self, attr, value):
        if attr == 'dc_bound':
            return self._dc_bound
        # noinspection PyProtectedMember
        return super(TemplateSerializer, self)._normalize(attr, value)

    def validate_alias(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            validate_alias(self.object, value)

        return attrs

    def validate(self, attrs):
        if self.request.method == 'POST' and self._dc_bound:
            limit = self._dc_bound.settings.VMS_TEMPLATE_LIMIT

            if limit is not None:
                if VmTemplate.objects.filter(dc_bound=self._dc_bound).count() >= int(limit):
                    raise s.ValidationError(_('Maximum number of server templates reached.'))

        try:
            ostype = attrs['ostype']
        except KeyError:
            ostype = self.object.ostype

        try:
            vm_define = attrs['vm_define']
        except KeyError:
            vm_define = self.object.vm_define

        vm_define_ostype = vm_define.get('ostype', None)

        # The template object itself has an ostype field, which is used to limit the use of a template on the DB level;
        # However, also the template.vm_define property can have an ostype attribute, which will be used for a new VM
        # (=> will be inherited from the template). A different ostype in both places will lead to strange situations
        # (e.g. using a Windows template, which will create a Linux VM). Therefore we have to prevent such situations.
        if vm_define_ostype is not None and ostype != vm_define_ostype:
            raise s.ValidationError('Mismatch between vm_define ostype and template ostype.')

        return super(TemplateSerializer, self).validate(attrs)


class ExtendedTemplateSerializer(TemplateSerializer):
    dcs = s.DcsField()
