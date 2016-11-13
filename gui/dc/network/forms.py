from django import forms
from django.utils.translation import ungettext_lazy, ugettext_lazy as _
from django.utils.six import text_type

# noinspection PyCompatibility
import ipaddress

from api.dc.network.views import dc_network
from api.network.base.views import net_manage
from api.network.ip.views import net_ip, net_ip_list
from api.vm.utils import get_owners
from gui.forms import SerializerForm
from gui.fields import ArrayField
from gui.widgets import ArrayWidget
from vms.models import Subnet, IPAddress, DefaultDc

TEXT_INPUT_ATTRS = {'class': 'input-transparent narrow', 'required': 'required'}
SELECT_ATTRS = {'class': 'narrow input-select2'}


class DcNetworkForm(SerializerForm):
    """
    Create or remove DC<->Subnet link by calling dc_network.
    """
    _api_call = dc_network

    name = forms.ChoiceField(label=_('Network'), required=True,
                             widget=forms.Select(attrs={'class': 'input-select2 narrow disable_created2'}))

    def __init__(self, request, networks, *args, **kwargs):
        super(DcNetworkForm, self).__init__(request, None, *args, **kwargs)
        self.fields['name'].choices = networks.values_list('name', 'alias')


class AdminNetworkForm(SerializerForm):
    """
    Create Subnet by calling net_manage.
    """
    _api_call = net_manage
    network = None
    netmask = None

    dc_bound = forms.BooleanField(label=_('DC-bound?'), required=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    name = forms.CharField(label=_('Name'), max_length=32, required=True,
                           widget=forms.TextInput(attrs={'class': 'input-transparent narrow disable_created',
                                                         'required': 'required', 'pattern': '[A-Za-z0-9\._-]+'}))
    alias = forms.CharField(label=_('Alias'), required=True, max_length=32,
                            widget=forms.TextInput(attrs=TEXT_INPUT_ATTRS))
    owner = forms.ChoiceField(label=_('Owner'), required=False,
                              widget=forms.Select(attrs=SELECT_ATTRS))
    access = forms.TypedChoiceField(label=_('Access'), required=False, coerce=int, choices=Subnet.ACCESS,
                                    widget=forms.Select(attrs=SELECT_ATTRS))
    desc = forms.CharField(label=_('Description'), max_length=128, required=False,
                           widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))
    ip_network = forms.CharField(label=_('Network/Netmask'), required=True, max_length=34,
                                 help_text=_('IPv4 network address with netmask in CIDR format.'),
                                 widget=forms.TextInput(attrs=TEXT_INPUT_ATTRS))  # IP address validated in serializer
    gateway = forms.CharField(label=_('Gateway'), required=False, max_length=32,
                              help_text=_('IPv4 gateway in quad-dotted format.'),
                              widget=forms.TextInput(attrs=TEXT_INPUT_ATTRS))  # IP address is validated in serializer
    vlan_id = forms.IntegerField(label=_('VLAN ID'), required=True, widget=forms.TextInput(attrs=TEXT_INPUT_ATTRS),
                                 help_text=_('802.1Q virtual LAN ID (0 - 4096, 0 = none).'))
    nic_tag = forms.ChoiceField(label=_('NIC Tag'), required=True,
                                help_text=_('NIC tag or device name on compute node.'),
                                widget=forms.Select(attrs=SELECT_ATTRS))

    # Advanced options
    resolvers = ArrayField(label=_('Resolvers'), required=False,
                           help_text=_('Comma-separated list of IPv4 addresses that can be used as resolvers.'),
                           widget=ArrayWidget(attrs={'class': 'input-transparent narrow'}))
    # dns_domain = forms.CharField(label=_('DNS Domain'), required=False,
    #                             help_text=_('Existing domain name used for creating A records for virtual servers'),
    #                             widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))
    ptr_domain = forms.CharField(label=_('PTR Domain'), required=False,
                                 help_text=_('Existing in-addr.arpa domain used for creating PTR associations with '
                                             'virtual servers.'),
                                 widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))
    dhcp_passthrough = forms.BooleanField(label=_('DHCP Passthrough'), required=False,
                                          help_text=_('When enabled, IP addresses for this network are managed by '
                                                      'an external DHCP service.'),
                                          widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))

    def __init__(self, request, net, *args, **kwargs):
        super(AdminNetworkForm, self).__init__(request, net, *args, **kwargs)
        self.fields['owner'].choices = get_owners(request).values_list('username', 'username')
        self.fields['nic_tag'].choices = [(i, i) for i in sorted(DefaultDc().settings.VMS_NET_NIC_TAGS)]

        if not request.user.is_staff:
            self.fields['dc_bound'].widget.attrs['disabled'] = 'disabled'

    def clean_ip_network(self):
        try:
            n = '/'.join(map(str.strip, str(self.cleaned_data.get('ip_network')).split('/')))
            net = ipaddress.ip_network(text_type(n))
        except ValueError:
            raise forms.ValidationError(_('Enter valid IPv4 network and netmask.'))
        else:
            self.network, self.netmask = net.with_netmask.split('/')

        return text_type(net)

    def _initial_data(self, request, obj):
        return obj.web_data_admin

    def _set_custom_api_errors(self, errors):
        # ip_network field does not exist in NetworkSerializer
        # network and netmask errors must be set to ip_network field
        network_errors = errors.get('network', [])
        netmask_errors = errors.get('netmask', [])

        if network_errors or netmask_errors:
            if network_errors == netmask_errors:
                ip_network_errors = network_errors
            else:
                ip_network_errors = network_errors + netmask_errors

            self._errors['ip_network'] = self.error_class(ip_network_errors)
            # The ip_network will not probably be in cleaned_data, but just in case remove it here
            try:
                del self.cleaned_data['ip_network']
            except KeyError:
                pass

    def _final_data(self, data=None):
        ret = super(AdminNetworkForm, self)._final_data(data=data)
        ip_network = ret.pop('ip_network', None)

        if ip_network:
            ret['network'] = self.network
            ret['netmask'] = self.netmask

        if self.action == 'create':  # Add dc parameter when doing POST (required by api.db.utils.get_virt_object)
            ret['dc'] = self._request.dc.name

        return ret


class NetworkIPForm(SerializerForm):
    """
    Create, update or delete network IP address.
    """
    _ip = None
    _count = 0
    _api_call = net_ip
    template = 'gui/dc/network_ip_form.html'

    ip = forms.GenericIPAddressField(label=_('IPv4 address'), required=True, protocol='ipv4',
                                     widget=forms.TextInput(attrs={'class': 'input-transparent narrow disable_created',
                                                                   'required': 'required', 'pattern': '[0-9\.]+'}))
    count = forms.IntegerField(label=_('Count'), required=False, min_value=1, max_value=254,
                               help_text=_('Number of IP addresses to create.'),
                               widget=forms.TextInput(attrs={'class': 'input-transparent narrow', 'required': ''}))
    usage = forms.TypedChoiceField(label=_('Usage'), required=False, choices=IPAddress.USAGE, coerce=int,
                                   widget=forms.Select(attrs=SELECT_ATTRS))
    note = forms.CharField(label=_('Note'), max_length=128, required=False,
                           widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))

    def __init__(self, request, net, ip, *args, **kwargs):
        self.net = net
        super(NetworkIPForm, self).__init__(request, ip, *args, **kwargs)

    def _initial_data(self, request, obj):
        return obj.web_data

    def clean(self):
        data = super(NetworkIPForm, self).clean()
        count = data.pop('count', 0)
        ip = data.pop('ip', None)

        if not ip:  # Cannot continue without ip
            return data

        if count and count > 1:
            ips = []
            i = 0

            for ipaddr in self.net.ip_network.hosts():  # iterator
                ipaddr = text_type(ipaddr)
                i4 = ipaddr.split('.')[-1]

                # Although these are valid IP addresses it is kind of unusual to use these IPs for virtual machines
                if i4 == '0' or i4 == '255':
                    continue

                if i or ipaddr == ip:
                    ips.append(ipaddr)
                    i += 1

                    if i >= count:
                        break

            if ips:
                data['ips'] = ips
                self._count = len(ips)
            else:
                self._errors['count'] = self.error_class([_('Invalid IP address range.')])

        else:
            self._count = 1
            self._ip = ip

        return data

    def api_call_args(self, net_name):
        if self._ip:
            self.__class__._api_call = net_ip
            return net_name, self._ip
        else:
            self.__class__._api_call = net_ip_list
            return net_name,

    def get_action_message(self):
        assert self.action in self._api_method, 'Unknown action'

        if self.action == 'update':
            return _('IP address was successfully updated')
        elif self.action == 'delete':
            return _('IP address was successfully deleted')
        else:
            return ungettext_lazy(
                'IP address was successfully created',
                '%(count)d IP addresses were successfully created',
                self._count
            ) % {'count': self._count}


class MultiNetworkIPForm(SerializerForm):
    """
    Delete multiple network IP addresses at once.
    """
    _api_call = net_ip_list
    template = 'gui/dc/network_ips_form.html'

    ips = ArrayField(required=True, widget=forms.HiddenInput())

    def __init__(self, request, net, ip, *args, **kwargs):
        self.net = net
        super(MultiNetworkIPForm, self).__init__(request, ip, *args, **kwargs)

    @staticmethod
    def api_call_args(net_name):
        return net_name,

    def get_action_message(self):
        assert self.action == 'delete', 'Unknown action'

        count = len(self.cleaned_data.get('ips', ()))

        return ungettext_lazy(
            'IP address was successfully deleted',
            '%(count)d IP addresses were successfully deleted',
            count
        ) % {'count': count}
