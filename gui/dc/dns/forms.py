from operator import and_
from functools import reduce
from django import forms
from django.db.models import Q
from django.utils.six import PY3
from django.utils.translation import ugettext_lazy as _

from api.dc.domain.views import dc_domain
from api.dns.domain.views import dns_domain
from api.dns.record.views import dns_record_list, dns_record
from api.vm.utils import get_owners
from gui.forms import SerializerForm
from gui.fields import ArrayField
from gui.widgets import NumberInput
from pdns.models import Domain, Record

TEXT_INPUT_ATTRS = {'class': 'input-transparent narrow', 'required': 'required'}
SELECT_ATTRS = {'class': 'narrow input-select2'}

if PY3:
    t_long = int
else:
    t_long = long  # noqa: F821


class DcDomainForm(SerializerForm):
    """
    Create or remove DC<->DNS Domain link by calling dc_domain.
    """
    _api_call = dc_domain

    name = forms.ChoiceField(label=_('Domain'), required=True,
                             widget=forms.Select(attrs={'class': 'input-select2 narrow disable_created2'}))

    def __init__(self, request, domains, *args, **kwargs):
        super(DcDomainForm, self).__init__(request, None, *args, **kwargs)
        self.fields['name'].choices = domains.values_list('name', 'name')

    def _final_data(self, data=None):
        return {}


class AdminDomainForm(SerializerForm):
    """
    Create DNS domain by calling dns_domain.
    """
    _api_call = dns_domain

    dc_bound = forms.BooleanField(label=_('DC-bound?'), required=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    name = forms.CharField(label=_('Name'), max_length=255, required=True,
                           widget=forms.TextInput(attrs={'class': 'input-transparent narrow disable_created',
                                                         'required': 'required', 'pattern': '[A-Za-z0-9._-]+'}))
    owner = forms.ChoiceField(label=_('Owner'), required=False,
                              widget=forms.Select(attrs=SELECT_ATTRS))
    access = forms.TypedChoiceField(label=_('Access'), required=False, coerce=int, choices=Domain.ACCESS,
                                    widget=forms.Select(attrs=SELECT_ATTRS))
    type = forms.ChoiceField(label=_('Type'), required=False, choices=Domain.TYPE_MASTER,
                             widget=forms.Select(attrs=SELECT_ATTRS),
                             help_text=_('PowerDNS domain type. '
                                         'MASTER - use DNS protocol messages to communicate changes '
                                         'with slaves. NATIVE - use database replication '
                                         'between master DNS server and slave DNS servers.'))
    desc = forms.CharField(label=_('Description'), max_length=128, required=False,
                           widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))
    tsig_keys = forms.CharField(label=_('TSIG Key(s)'), max_length=1000, required=False,
                                  widget=forms.TextInput(attrs={'class': 'input-transparent', 'required': ''}),
                                  help_text=_('TSIG DNS keys for external zone transfers. Zone transfers to '
                                              'external DNS slaves will only be allowed using this key. '
                                              'For more info on how to generate the key see Danube Cloud docs.'
                                              ))

    def __init__(self, request, domain, *args, **kwargs):
        super(AdminDomainForm, self).__init__(request, domain, *args, **kwargs)
        self.fields['owner'].choices = get_owners(request).values_list('username', 'username')

        if not request.user.is_staff:
            self.fields['dc_bound'].widget.attrs['disabled'] = 'disabled'

    def _initial_data(self, request, obj):
        return obj.web_data

    def _final_data(self, data=None):
        data = super(AdminDomainForm, self)._final_data(data=data)

        if self.action == 'create':  # Add dc parameter when doing POST (required by api.db.utils.get_virt_object)
            data['dc'] = self._request.dc.name

        return data


class DnsRecordFilterForm(forms.Form):
    """
    Filter DNS records for a domain.
    """
    all = forms.BooleanField(widget=forms.HiddenInput(attrs={'class': 'always-include-navigation'}), required=False)
    domain = forms.ChoiceField(label=_('Domain'), required=False,
                               widget=forms.Select(attrs={'class': 'fill-up input-navigation select-transparent '
                                                                   'always-include-navigation'}))
    type = forms.ChoiceField(label=_('Type'), required=False, choices=(('', _('Type (all)')),) + Record.TYPE_USED,
                             widget=forms.Select(attrs={'class': 'fill-up input-navigation select-transparent'}))
    name = forms.CharField(label=_('Name'), required=False,
                           widget=forms.TextInput(attrs={'class': 'fill-up input-navigation input-transparent',
                                                         'placeholder': _('Search by name')}))
    content = forms.CharField(label=_('Content'), required=False,
                              widget=forms.TextInput(attrs={'class': 'fill-up input-navigation input-transparent',
                                                            'placeholder': _('Search by content')}))
    changed_since = forms.DateField(label=_('Changed since'), required=False, input_formats=('%Y-%m-%d',),
                                    widget=forms.DateInput(format='%Y-%m-%d',
                                                           attrs={'placeholder': _('Changed since'),
                                                                  'class': 'fill-up input-navigation input-transparent '
                                                                  'input-date'}))

    def __init__(self, request, data, _all=False, **kwargs):
        super(DnsRecordFilterForm, self).__init__(data, **kwargs)
        domains = Domain.objects.order_by('name')
        user, dc = request.user, request.dc

        if request.GET.get('deleted', False):
            domains = domains.exclude(access=Domain.INTERNAL)
        else:
            domains = domains.exclude(access__in=Domain.INVISIBLE)

        if user.is_staff and _all:
            domain_choices = [(d.name, d.name) for d in domains]
        else:
            dc_domain_ids = list(dc.domaindc_set.values_list('domain_id', flat=True))
            domains = domains.filter(Q(id__in=dc_domain_ids) | Q(user=user.id))
            domain_choices = [(d.name, d.name) for d in domains
                              if (user.is_staff or d.user == user.id or d.dc_bound == dc.id)]

        self.fields['domain'].choices = domain_choices

    def get_filters(self):
        data = self.cleaned_data
        query = []

        _type = data.get('type')
        if _type:
            query.append(Q(type=_type))

        name = data.get('name')
        if name:
            query.append(Q(name__icontains=name))

        content = data.get('content')
        if content:
            query.append(Q(content__icontains=content))

        changed_since = data.get('changed_since')
        if changed_since:
            query.append(Q(change_date__gte=changed_since.strftime('%s')))

        if query:
            return reduce(and_, query)
        else:
            return None


class DnsRecordForm(SerializerForm):
    """
    Create, update or delete network DNS record.
    """
    _ip = None
    _api_call = dns_record
    template = 'gui/dc/domain_record_form.html'

    id = forms.IntegerField(label=_('ID'), required=True, widget=forms.HiddenInput())
    name = forms.CharField(label=_('Name'), required=True,
                           help_text=_('The full URI the DNS server should pick up on.'),
                           widget=forms.TextInput(attrs=TEXT_INPUT_ATTRS))
    content = forms.CharField(label=_('Content'), required=False,
                              # help_text=_('The answer of the DNS query.'),
                              widget=forms.TextInput(attrs={'class': 'input-transparent narrow'}))
    type = forms.ChoiceField(label=_('Type'), required=True, choices=Record.TYPE_USED,
                             widget=forms.Select(attrs=SELECT_ATTRS))
    ttl = forms.IntegerField(label=_('TTL'), required=False,
                             help_text=_('How long the DNS client is allowed to remember this record.'),
                             widget=NumberInput(attrs={'class': 'input-transparent narrow'}))
    prio = forms.IntegerField(label=_('Priority'), required=False,
                              # help_text=_('Priority used by some record types.'),
                              widget=NumberInput(attrs={'class': 'input-transparent narrow'}))
    disabled = forms.BooleanField(label=_('Disabled?'), required=False,
                                  help_text=_('If set to true, this record is hidden from DNS clients.'),
                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))

    def __init__(self, request, domain, record, *args, **kwargs):
        self.domain = domain
        super(DnsRecordForm, self).__init__(request, record, *args, **kwargs)

    def _initial_data(self, request, obj):
        return obj.web_data

    def api_call_args(self, domain_name):
        if self.action == 'create':
            return domain_name,
        else:
            return domain_name, self.cleaned_data['id']


class MultiDnsRecordForm(SerializerForm):
    """
    Delete multiple DNS records at once.
    """
    _api_call = dns_record_list
    template = 'gui/dc/domain_records_form.html'

    records = ArrayField(required=True, widget=forms.HiddenInput())

    def __init__(self, request, domain, record, *args, **kwargs):
        self.domain = domain
        super(MultiDnsRecordForm, self).__init__(request, record, *args, **kwargs)

    @staticmethod
    def api_call_args(domain_name):
        return domain_name,
