from api import serializers as s
from pdns.models import Domain, TsigKey
from pdns.validators import validate_dns_name
from vms.models import Dc
from gui.models import User


class TsigKeySerializer(s.InstanceSerializer):
    """
    pdns.models.TsigKey
    """
    _model_ = TsigKey
    _update_fields_ = ('name', 'algorithm', 'secret')

    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._/-]*$', max_length=250, min_length=3, required=False)
    algorithm = s.ChoiceField(choices=TsigKey.ALGORITHM, required=False)
    secret = s.SafeCharField(max_length=250, required=False)


class DomainSerializer(s.ConditionalDCBoundSerializer):
    """
    pdns.models.Domain
    """
    _model_ = Domain
    _update_fields_ = ('owner', 'access', 'desc', 'dc_bound', 'type')
    _default_fields_ = ('name', 'owner', 'type')
    _blank_fields_ = frozenset({'desc'})
    name_changed = None

    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._/-]*$', max_length=253, min_length=3)
    type = s.ChoiceField(choices=Domain.TYPE_MASTER, default=Domain.MASTER)
    owner = s.SlugRelatedField(slug_field='username', queryset=User.objects)
    access = s.IntegerChoiceField(choices=Domain.ACCESS, default=Domain.PRIVATE)
    desc = s.SafeCharField(max_length=128, required=False)
    created = s.DateTimeField(read_only=True, required=False)

    def __init__(self, request, domain, *args, **kwargs):
        super(DomainSerializer, self).__init__(request, domain, *args, **kwargs)
        if not kwargs.get('many', False):
            self._dc_bound = domain.dc_bound

    def _normalize(self, attr, value):
        if attr == 'dc_bound':
            if isinstance(self._dc_bound, Dc):
                self._dc_bound = self._dc_bound.id
            return self._dc_bound
        # noinspection PyProtectedMember
        return super(DomainSerializer, self)._normalize(attr, value)

    def validate_name(self, attrs, source):
        try:
            value = attrs[source].lower()  # The domain name must be always lowercased (DB requirement)
        except KeyError:
            pass
        else:
            attrs[source] = value  # Save lowercased domain name

            if self.object.pk:
                if self.object.name == value:
                    return attrs
                else:
                    self.name_changed = self.object.name  # Save old domain name

            validate_dns_name(value)

        return attrs


class ExtendedDomainSerializer(DomainSerializer):
    dcs = s.DcsField()
    records = s.IntegerField(read_only=True)
