from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from frozendict import frozendict

from api import serializers as s
from api.validators import validate_alias, validate_dc_bound
from api.vm.utils import get_owners
from gui.models import User
from vms.models import Subnet, IPAddress, DefaultDc
from pdns.models import Domain


class NetworkSerializer(s.InstanceSerializer):
    """
    vms.models.Subnet
    """
    _model_ = Subnet
    _update_fields_ = ('alias', 'owner', 'access', 'desc', 'network', 'netmask', 'gateway', 'resolvers',
                       'dns_domain', 'ptr_domain', 'nic_tag', 'vlan_id', 'dc_bound', 'dhcp_passthrough')
    _default_fields_ = ('name', 'alias', 'owner')
    _blank_fields_ = frozenset({'desc', 'dns_domain', 'ptr_domain'})
    _null_fields_ = frozenset({'gateway'})

    # min_length because of API URL: /network/ip/
    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', min_length=3, max_length=32)
    alias = s.SafeCharField(max_length=32)
    owner = s.SlugRelatedField(slug_field='username', queryset=User.objects, required=False)
    access = s.IntegerChoiceField(choices=Subnet.ACCESS, default=Subnet.PRIVATE)
    desc = s.SafeCharField(max_length=128, required=False)
    network = s.IPAddressField()
    netmask = s.IPAddressField()
    gateway = s.IPAddressField(required=False)  # can be null
    nic_tag = s.ChoiceField()
    vlan_id = s.IntegerField(min_value=0, max_value=4096)
    resolvers = s.IPAddressArrayField(source='resolvers_api', required=False, max_items=8)
    dns_domain = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=250, required=False)  # can be blank
    ptr_domain = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=250, required=False)  # can be blank
    dhcp_passthrough = s.BooleanField()
    dc_bound = s.BooleanField(source='dc_bound_bool', default=True)
    created = s.DateTimeField(read_only=True, required=False)

    def __init__(self, request, net, *args, **kwargs):
        super(NetworkSerializer, self).__init__(request, net, *args, **kwargs)
        if not kwargs.get('many', False):
            self._dc_bound = net.dc_bound
            self.fields['owner'].queryset = get_owners(request, all=True)
            self.fields['nic_tag'].choices = [(i, i) for i in DefaultDc().settings.VMS_NET_NIC_TAGS]

    def _normalize(self, attr, value):
        if attr == 'dc_bound':
            return self._dc_bound
        # noinspection PyProtectedMember
        return super(NetworkSerializer, self)._normalize(attr, value)

    def validate_dc_bound(self, attrs, source):
        try:
            value = bool(attrs[source])
        except KeyError:
            pass
        else:
            if value != self.object.dc_bound_bool:
                self._dc_bound = validate_dc_bound(self.request, self.object, value, _('Network'))

        return attrs

    def validate_alias(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            validate_alias(self.object, value)

        return attrs

    def validate_vlan_id(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            net = self.object

            if not net.new:
                # TODO: Cannot use ip__in=net_ips (ProgrammingError)
                net_ips = set(net.ipaddress_set.all().values_list('ip', flat=True))
                other_ips = set(IPAddress.objects.exclude(subnet=net).filter(subnet__vlan_id=int(value))
                                                                     .values_list('ip', flat=True))
                if net_ips.intersection(other_ips):
                    raise s.ValidationError(_('Network has IP addresses that already exist in another '
                                              'network with the same VLAN ID.'))

        return attrs

    # noinspection PyMethodMayBeStatic
    def validate_ptr_domain(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if value:
                if not value.endswith('in-addr.arpa'):
                    raise s.ValidationError(_('Invalid PTR domain name.'))
                if settings.DNS_ENABLED:
                    if not Domain.objects.filter(name=value).exists():
                        raise s.ObjectDoesNotExist(value)

        return attrs

    def validate(self, attrs):
        try:
            network = attrs['network']
        except KeyError:
            network = self.object.network

        try:
            netmask = attrs['netmask']
        except KeyError:
            netmask = self.object.netmask

        try:
            ip_network = Subnet.get_ip_network(network, netmask)
            if ip_network.is_reserved:
                raise ValueError
        except ValueError:
            self._errors['network'] = self._errors['netmask'] = \
                s.ErrorList([_('Enter a valid IPv4 network and netmask.')])

        if self.request.method == 'POST' and self._dc_bound:
            limit = self._dc_bound.settings.VMS_NET_LIMIT

            if limit is not None:
                if Subnet.objects.filter(dc_bound=self._dc_bound).count() >= int(limit):
                    raise s.ValidationError(_('Maximum number of networks reached'))

        if self._dc_bound:
            try:
                vlan_id = attrs['vlan_id']
            except KeyError:
                vlan_id = self.object.vlan_id

            dc_settings = self._dc_bound.settings

            if dc_settings.VMS_NET_VLAN_RESTRICT and vlan_id not in dc_settings.VMS_NET_VLAN_ALLOWED:
                self._errors['vlan_id'] = s.ErrorList([_('VLAN ID is not available in datacenter.')])

        return attrs

    # noinspection PyMethodMayBeStatic
    def update_errors(self, fields, err_msg):
        errors = {}
        for i in fields:
            errors[i] = s.ErrorList([err_msg])
        return errors


class ExtendedNetworkSerializer(NetworkSerializer):
    _free_ip_subquery = '''"vms_ipaddress"."vm_id" is NULL AND "vms_ipaddress"."usage" = %d''' % IPAddress.VM
    ips_free_query = 'SELECT COUNT(*) FROM "vms_ipaddress" WHERE "vms_subnet"."uuid" = "vms_ipaddress"."subnet_id" '\
                     'AND %s' % _free_ip_subquery
    ips_used_query = 'SELECT COUNT(*) FROM "vms_ipaddress" WHERE "vms_subnet"."uuid" = "vms_ipaddress"."subnet_id" '\
                     'AND NOT (%s)' % _free_ip_subquery
    extra_select = frozendict({'ips_free': ips_free_query, 'ips_used': ips_used_query})

    dcs = s.DcsField()
    ips_free = s.IntegerField(read_only=True)
    ips_used = s.IntegerField(read_only=True)
