from __future__ import absolute_import

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.six import text_type
# noinspection PyCompatibility
import ipaddress

from vms.models.vm import Vm
from vms.models.subnet import Subnet


class IPAddress(models.Model):
    """
    IP address.
    """
    _nic = None  # cache [nic_id, nic_object] pair

    VM = 1  # Server usage (IP is only in DB)
    VM_REAL = 2  # Server usage (IP is set on server on hypervisor)
    NODE = 3  # Compute node usage
    OTHER = 9

    USAGE = (
        (VM, _('Server')),
        (OTHER, _('Other')),
    )
    USAGE_REAL = USAGE + (
        (NODE, _('Node')),
        (VM_REAL, _('Server')),
    )

    ip = models.GenericIPAddressField(_('IP Address'))
    subnet = models.ForeignKey(Subnet, verbose_name=_('Subnet'))
    vm = models.ForeignKey(Vm, null=True, blank=True, default=None, on_delete=models.SET_NULL, verbose_name=_('Server'))
    vms = models.ManyToManyField(Vm, blank=True, verbose_name=_('Servers'), related_name='allowed_ips')
    usage = models.SmallIntegerField(_('Usage'), choices=USAGE_REAL, default=VM, db_index=True)
    note = models.CharField(_('Note'), max_length=255, blank=True)

    class Meta:
        app_label = 'vms'
        verbose_name = _('IP address')
        verbose_name_plural = _('IP addresses')
        unique_together = (('ip', 'subnet'),)

    def __unicode__(self):
        return '%s@%s' % (self.ip, self.subnet.name)

    @staticmethod
    def get_ip_address(ipaddr):
        return ipaddress.ip_address(text_type(ipaddr))

    @staticmethod
    def get_net_address(ipaddr, netmask):
        """Computes network address from any IP address and netmask"""
        return text_type(ipaddress.IPv4Network(u'%s/%s' % (ipaddr, netmask), strict=False).network_address)

    def is_node_address(self):
        return self.usage == self.NODE

    @property
    def ip_address(self):
        return self.ip_address(self.ip)

    def get_ip_interface(self, ipaddr):
        return ipaddress.ip_interface(text_type(ipaddr + '/' + self.subnet.netmask))

    @property
    def ip_interface(self):
        return self.ip_interface(self.ip)

    @property
    def vm_uuid(self):
        if self.vm:
            return self.vm.uuid
        else:
            return None

    @property
    def hostname(self):
        if self.usage == self.NODE:
            return self.note
        elif self.vm:
            return self.vm.hostname
        else:
            return None

    @property
    def additional_vm_uuids(self):
        if self.pk and self.usage in (self.VM, self.VM_REAL):
            return [vm.uuid for vm in self.vms.all()]  # Faster because of prefetch_related('vms')
        else:
            return []

    @property
    def additional_vm_hostnames(self):
        if self.pk and self.usage in (self.VM, self.VM_REAL):
            return [vm.hostname for vm in self.vms.all()]  # Faster because of prefetch_related('vms')
        else:
            return []

    @property
    def api_note(self):
        if self.usage == self.NODE:
            return ''
        return self.note

    @api_note.setter
    def api_note(self, value):
        if self.usage != self.NODE:
            self.note = value

    def get_nic(self):
        """Return VM's NIC associated with this IP address"""
        if self.vm and self.ip and self.subnet:
            ip = str(self.ip)
            uuid = self.subnet.uuid

            for nic_id, nic in enumerate(self.vm.json_get_nics(), start=1):
                if nic.get('network_uuid', None) == uuid and nic.get('ip', None) == ip:
                    return nic_id, nic

        return None, {}

    @property
    def mac(self):  # NetworkIPSerializer
        if self._nic is None:
            self._nic = self.get_nic()
        return self._nic[1].get('mac', '')

    @property
    def nic_id(self):  # NetworkIPSerializer
        if self._nic is None:
            self._nic = self.get_nic()
        return self._nic[0]

    @property
    def web_usage(self):  # NetworkIPForm
        # Fake server (2) usage (always show 1 for any server) - bug #chili-615
        if self.usage == self.VM_REAL:
            return self.VM
        return self.usage

    @property
    def web_data(self):  # NetworkIPForm
        return {'ip': self.ip, 'usage': self.web_usage, 'note': self.note}
