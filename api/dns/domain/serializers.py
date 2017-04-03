from django.utils.translation import ugettext_lazy as _

from api import serializers as s
from api.validators import validate_dc_bound
from pdns.models import Domain
from pdns.validators import validate_dns_name
from gui.models import User


class DomainSerializer(s.InstanceSerializer):
    """
    pdns.models.Domain
    """
    _model_ = Domain
    _update_fields_ = ('owner', 'access', 'desc', 'dc_bound')
    _default_fields_ = ('name', 'owner')
    _blank_fields_ = frozenset({'desc'})
    name_changed = None

    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._/-]*$', max_length=253, min_length=3)
    owner = s.SlugRelatedField(slug_field='username', queryset=User.objects)
    access = s.IntegerChoiceField(choices=Domain.ACCESS, default=Domain.PRIVATE)
    desc = s.SafeCharField(max_length=128, required=False)
    created = s.DateTimeField(read_only=True, required=False)
    dc_bound = s.BooleanField(source='dc_bound_bool', default=True)

    def __init__(self, request, domain, *args, **kwargs):
        super(DomainSerializer, self).__init__(request, domain, *args, **kwargs)
        if not kwargs.get('many', False):
            self._dc_bound = domain.dc_bound

    def _normalize(self, attr, value):
        if attr == 'dc_bound':
            return self._dc_bound
        # noinspection PyProtectedMember
        return super(DomainSerializer, self)._normalize(attr, value)

    def validate_dc_bound(self, attrs, source):
        try:
            value = bool(attrs[source])
        except KeyError:
            pass
        else:
            if value != self.object.dc_bound_bool:
                dc = validate_dc_bound(self.request, self.object, value, _('Domain'))

                if dc:
                    self._dc_bound = dc.id
                else:
                    self._dc_bound = None

        return attrs

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
