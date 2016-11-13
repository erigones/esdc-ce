# noinspection PyCompatibility
import ipaddress

from django.utils.translation import ugettext_lazy as _
from django.utils.six import text_type

from api import serializers as s
from vms.models import IPAddress


class NetworkIPSerializer(s.Serializer):
    """
    vms.models.IPAddress
    """
    ip = s.IPAddressField(strict=True)
    hostname = s.CharField(read_only=True, required=False)
    dc = s.CharField(source='vm.dc', read_only=True, required=False)
    mac = s.CharField(read_only=True, required=False)
    nic_id = s.IntegerField(read_only=True, required=False)
    usage = s.IntegerChoiceField(choices=IPAddress.USAGE, default=IPAddress.VM)
    note = s.SafeCharField(source='api_note', required=False, max_length=128)

    def __init__(self, net, *args, **kwargs):
        self.net = net
        super(NetworkIPSerializer, self).__init__(*args, **kwargs)

    def restore_object(self, attrs, instance=None):
        if instance is None:  # POST
            instance = IPAddress(subnet=self.net, ip=attrs['ip'])

        if 'api_note' in attrs:
            note = attrs['api_note']
            if note:
                instance.api_note = note
            else:
                instance.api_note = ''

        usage = attrs.get('usage', None)
        if usage:
            instance.usage = usage

        return instance

    def validate_ip(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            return attrs

        net = self.net
        # Was already validated by IPAddressField
        ipaddr = ipaddress.ip_address(text_type(value))
        network = net.ip_network

        if ipaddr not in network:
            raise s.ValidationError(_('IP address "%(ip)s" does not belong to network %(net)s.') %
                                    {'ip': value, 'net': net.name})

        # Check if IP does not exist in another network with same VLAN ID
        if IPAddress.objects.exclude(subnet=net).filter(ip=value, subnet__vlan_id=net.vlan_id).exists():
            raise s.ValidationError(_('IP address "%(ip)s" already exists in another network with the same VLAN ID.') %
                                    {'ip': value})

        return attrs

    def validate_usage(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object and self.object.vm and value != IPAddress.VM:
                raise s.ValidationError(_('IP address is already used by some VM.'))

        return attrs

    def validate(self, attrs):
        if self.object and self.object.is_node_address():
            raise s.ValidationError(_('IP address is used by Compute node.'))

        return attrs


class NetworkIPPlanSerializer(NetworkIPSerializer):
    """
    Read-only serializer. Includes subnet/netmask and network name to NetworkIPSerializer.
    """
    net = s.Field(source='subnet.name')
    subnet = s.Field(source='subnet.ip_network.with_prefixlen')
    vlan_id = s.IntegerField(source='subnet.vlan_id', read_only=True)
