from __future__ import absolute_import

from django.db import models
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from uuid import uuid4
# noinspection PyCompatibility
import ipaddress

# noinspection PyProtectedMember
from vms.mixins import _DcMixin
# noinspection PyProtectedMember
from vms.models.base import _VirtModel, _UserTasksModel
from vms.models.vm import Vm
from vms.models.node import Node


class Subnet(_VirtModel, _DcMixin, _UserTasksModel):
    """
    Sub-network.
    """
    ACCESS = (
        (_VirtModel.PUBLIC, _('Public')),
        (_VirtModel.PRIVATE, _('Private')),
        (_VirtModel.DELETED, _('Deleted')),
    )

    new = False
    _pk_key = 'subnet_id'  # _UserTasksModel

    # Inherited: name, alias, owner, desc, access, created, changed, dc, dc_bound
    uuid = models.CharField(_('UUID'), max_length=36, primary_key=True)
    nic_tag = models.CharField(_('NIC Tag'), max_length=32, default='admin')
    vlan_id = models.SmallIntegerField(_('VLAN ID'), default=0)
    network = models.GenericIPAddressField(_('Network'))
    netmask = models.GenericIPAddressField(_('Netmask'))
    gateway = models.GenericIPAddressField(_('Gateway'), null=True, blank=True)
    resolvers = models.CharField(_('Resolvers'), max_length=255, blank=True,
                                 help_text=_('List of DNS servers separated by commas.'))
    dns_domain = models.CharField(_('DNS Domain'), max_length=255, blank=True,
                                  help_text=_('DNS search domain.'))
    ptr_domain = models.CharField(_('PTR Domain'), max_length=255, blank=True,
                                  help_text=_('Name of a Pdns Domain.'))
    dhcp_passthrough = models.BooleanField(_('DHCP Passthrough'), default=False)
    vxlan_id = models.PositiveIntegerField(_('VXLAN segment ID'), null=True, blank=True, default=None)
    mtu = models.PositiveIntegerField(_('MTU'), null=True, blank=True, default=None)

    class Meta:
        app_label = 'vms'
        verbose_name = _('Network')
        verbose_name_plural = _('Networks')
        unique_together = (('alias', 'owner'),)
        index_together = (('network', 'netmask'),)

    def __init__(self, *args, **kwargs):
        super(Subnet, self).__init__(*args, **kwargs)
        if not self.uuid:
            self.new = True
            self.uuid = str(uuid4())

    @staticmethod
    def get_ip_network(netaddr, netmask):
        return ipaddress.ip_network(u'%s/%s' % (netaddr, netmask))

    @staticmethod
    def get_ip_network_hostinfo(net):
        netaddr = int(net.network_address)
        bcastaddr = int(net.broadcast_address)
        return {
            'min': ipaddress.IPv4Address(netaddr + 1),
            'max': ipaddress.IPv4Address(bcastaddr - 1),
            'hosts': bcastaddr - netaddr - 1
        }

    @property
    def ip_network(self):
        return self.get_ip_network(self.network, self.netmask)

    @property
    def ip_network_hostinfo(self):
        return self.get_ip_network_hostinfo(self.ip_network)

    def get_resolvers(self):
        resolvers = str(self.resolvers).strip()

        if not resolvers:
            return []

        return [i.strip() for i in resolvers.split(',')]

    def set_resolvers(self, value):
        if not value:
            self.resolvers = ''
        if isinstance(value, (list, tuple, set)):
            self.resolvers = ','.join(value)
        else:
            self.resolvers = value

    resolvers_api = property(get_resolvers, set_resolvers)

    @property
    def nic_tag_type(self):
        """Return type of the NIC tag"""
        # return type of the nictag or empty string if self.nic_tag is not found in Node.all_nictags
        return Node.all_nictags().get(self.nic_tag, '')

    @property
    def web_data(self):
        """Return dict used in server web templates"""
        return {'dhcp_passthrough': self.dhcp_passthrough}

    @property
    def web_data_admin(self):
        """Return dict used in admin/DC web templates"""
        return {
            'name': self.name,
            'alias': self.alias,
            'access': self.access,
            'owner': self.owner.username,
            'desc': self.desc,
            'ip_network': str(self.ip_network),
            'network': self.network,
            'netmask': self.netmask,
            'gateway': self.gateway,
            'nic_tag': self.nic_tag,
            'nic_tag_type': self.nic_tag_type,
            'vlan_id': self.vlan_id,
            'resolvers': self.get_resolvers(),
            'dns_domain': self.dns_domain,
            'ptr_domain': self.ptr_domain,
            'dc_bound': self.dc_bound_bool,
            'dhcp_passthrough': self.dhcp_passthrough,
        }

    def is_used_by_vms(self, dc=None):
        # Since this function returns a boolean value, we can use the association between an IPAddress and a VM
        # to quickly find out whether there is a VM that uses this Subnet. In case there is no relationship we
        # have to inspect each VM's json (and json_active) in order to find used network uuids and compare them
        # to this subnet's uuid.
        if dc:
            if dc.vm_set.filter(ipaddress__subnet=self).exists():  # Quick check
                return True
            vms = dc.vm_set.all()
        else:
            if self.ipaddress_set.filter(Q(vm__isnull=False) | ~Q(vms=None)).exists():  # Quick check
                return True
            vms = Vm.objects.filter(dc__in=self.dc.all())

        for vm in vms:  # Deep check because VMs can use networks without IP addresses (dhcp_passthrough)
            if self.uuid in vm.get_network_uuids():
                return True

        return False
