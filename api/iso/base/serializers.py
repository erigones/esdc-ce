from django.utils.translation import ugettext_lazy as _

from api import serializers as s
from api.validators import validate_alias
from api.vm.utils import get_owners
from gui.models import User
from vms.models import Iso


class IsoSerializer(s.ConditionalDCBoundSerializer):
    """
    vms.models.Iso
    """
    _model_ = Iso
    _update_fields_ = ('alias', 'owner', 'access', 'desc', 'ostype', 'dc_bound')
    _default_fields_ = ('name', 'alias', 'owner')
    _null_fields_ = frozenset({'ostype'})

    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=32)
    alias = s.SafeCharField(max_length=32)
    owner = s.SlugRelatedField(slug_field='username', queryset=User.objects)
    access = s.IntegerChoiceField(choices=Iso.ACCESS, default=Iso.PRIVATE)
    desc = s.SafeCharField(max_length=128, required=False)
    ostype = s.IntegerChoiceField(choices=Iso.OSTYPE, required=False)
    created = s.DateTimeField(read_only=True, required=False)

    def __init__(self, request, iso, *args, **kwargs):
        super(IsoSerializer, self).__init__(request, iso, *args, **kwargs)
        if not kwargs.get('many', False):
            self._dc_bound = iso.dc_bound
            self.fields['owner'].queryset = get_owners(request, all=True)

    def _normalize(self, attr, value):
        if attr == 'dc_bound':
            return self._dc_bound
        # noinspection PyProtectedMember
        return super(IsoSerializer, self)._normalize(attr, value)

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
            limit = self._dc_bound.settings.VMS_ISO_LIMIT

            if limit is not None:
                if Iso.objects.filter(dc_bound=self._dc_bound).count() >= int(limit):
                    raise s.ValidationError(_('Maximum number of ISO images reached'))

        return attrs


class ExtendedIsoSerializer(IsoSerializer):
    dcs = s.DcsField()
