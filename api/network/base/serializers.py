from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from frozendict import frozendict

from api import serializers as s
from api.validators import validate_alias
from api.vm.utils import get_owners
from gui.models import User
from vms.models import Subnet, IPAddress, Node
from pdns.models import Domain


class NetworkSerializer(s.ConditionalDCBoundSerializer):
    """
    vms.models.Subnet
    """
    _model_ = Subnet
    _update_fields_ = ('alias', 'owner', 'access', 'desc', 'network', 'netmask', 'gateway', 'resolvers',
                       'dns_domain', 'ptr_domain', 'nic_tag', 'vlan_id', 'dc_bound', 'dhcp_passthrough', 'vxlan_id',
                       'mtu')
    _default_fields_ = ('name', 'alias', 'owner')
    _blank_fields_ = frozenset({'desc', 'dns_domain', 'ptr_domain'})
    _null_fields_ = frozenset({'gateway'})

    # min_length because of API URL: /network/ip/
    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', min_length=3, max_length=32)
    uuid = s.CharField(read_only=True)
    alias = s.SafeCharField(max_length=32)
    owner = s.SlugRelatedField(slug_field='username', queryset=User.objects, required=False)
    access = s.IntegerChoiceField(choices=Subnet.ACCESS, default=Subnet.PRIVATE)
    desc = s.SafeCharField(max_length=128, required=False)
    network = s.IPAddressField()
    netmask = s.IPAddressField()
    gateway = s.IPAddressField(required=False)  # can be null
    nic_tag = s.ChoiceField()
    nic_tag_type = s.CharField(read_only=True)
    vlan_id = s.IntegerField(min_value=0, max_value=4096)
    vxlan_id = s.IntegerField(min_value=1, max_value=16777215, required=False)  # (2**24 - 1) based on RFC 7348
    mtu = s.IntegerField(min_value=576, max_value=9000, required=False)  # values from man vmadm
    resolvers = s.IPAddressArrayField(source='resolvers_api', required=False, max_items=8)
    dns_domain = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=250, required=False)  # can be blank
    ptr_domain = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=250, required=False)  # can be blank
    dhcp_passthrough = s.BooleanField(default=False)
    created = s.DateTimeField(read_only=True, required=False)

    def __init__(self, request, net, *args, **kwargs):
        super(NetworkSerializer, self).__init__(request, net, *args, **kwargs)
        if not kwargs.get('many', False):
            self._dc_bound = net.dc_bound
            self.fields['owner'].queryset = get_owners(request, all=True)
            self.fields['nic_tag'].choices = Node.all_nictags_choices()

    def _normalize(self, attr, value):
        if attr == 'dc_bound':
            return self._dc_bound
        # noinspection PyProtectedMember
        return super(NetworkSerializer, self)._normalize(attr, value)

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
            vxlan_id = attrs['vxlan_id']
        except KeyError:
            vxlan_id = self.object.vxlan_id

        try:
            mtu = attrs['mtu']
        except KeyError:
            mtu = self.object.mtu

        try:
            nic_tag = attrs['nic_tag']
        except KeyError:
            nic_tag = self.object.nic_tag

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
                    raise s.ValidationError(_('Maximum number of networks reached.'))

        nic_tag_type = Node.all_nictags()[nic_tag]
        # retrieve all available nictags and see what is the type of the current nic tag
        # if type is overlay then vxlan is mandatory argument
        if nic_tag_type == 'overlay rule':
            if not vxlan_id:
                self._errors['vxlan_id'] = s.ErrorList([_('VXLAN ID is required when an '
                                                          'overlay NIC tag is selected.')])
        else:
            attrs['vxlan_id'] = None

        # validate MTU for overlays and etherstubs, and physical nics
        if nic_tag_type == 'overlay rule' and not mtu:
            # if MTU was not set for the overlay
            attrs['mtu'] = 1400

        if nic_tag_type in ('normal', 'aggr') and mtu and mtu < 1500:
            self._errors['mtu'] = s.ErrorList([_('MTU must be from integer interval [1500, 9000].')])

        if self._dc_bound:
            try:
                vlan_id = attrs['vlan_id']
            except KeyError:
                vlan_id = self.object.vlan_id

            dc_settings = self._dc_bound.settings

            if dc_settings.VMS_NET_VLAN_RESTRICT and vlan_id not in dc_settings.VMS_NET_VLAN_ALLOWED:
                self._errors['vlan_id'] = s.ErrorList([_('VLAN ID is not available in datacenter.')])

            if dc_settings.VMS_NET_VXLAN_RESTRICT and vxlan_id not in dc_settings.VMS_NET_VXLAN_ALLOWED:
                self._errors['vxlan_id'] = s.ErrorList([_('VXLAN ID is not available in datacenter.')])

        return super(NetworkSerializer, self).validate(attrs)

    # noinspection PyMethodMayBeStatic
    def update_errors(self, fields, err_msg):
        errors = {}
        for i in fields:
            errors[i] = s.ErrorList([err_msg])
        return errors


class ExtendedNetworkSerializer(NetworkSerializer):
    _free_ip_subquery = '"vms_ipaddress"."vm_id" IS NULL AND "vms_ipaddress"."usage" = %d '\
                        'AND "vms_ipaddress_vms"."vm_id" IS NULL' % IPAddress.VM

    ips_free_query = 'SELECT COUNT(*) FROM "vms_ipaddress" LEFT OUTER JOIN '\
                     '"vms_ipaddress_vms" ON ("vms_ipaddress"."id" = "vms_ipaddress_vms"."ipaddress_id") ' \
                     'WHERE "vms_subnet"."uuid" = "vms_ipaddress"."subnet_id" '\
                     'AND %s' % _free_ip_subquery

    ips_used_query = 'SELECT COUNT(*) FROM "vms_ipaddress" LEFT OUTER JOIN '\
                     '"vms_ipaddress_vms" ON ("vms_ipaddress"."id" = "vms_ipaddress_vms"."ipaddress_id") ' \
                     'WHERE "vms_subnet"."uuid" = "vms_ipaddress"."subnet_id" '\
                     'AND NOT (%s)' % _free_ip_subquery

    extra_select = frozendict({'ips_free': ips_free_query, 'ips_used': ips_used_query})

    dcs = s.DcsField()
    ips_free = s.IntegerField(read_only=True)
    ips_used = s.IntegerField(read_only=True)
