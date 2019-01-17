from django import forms
from django.utils.translation import ugettext_lazy as _

from api.dc.iso.views import dc_iso
from api.iso.base.views import iso_manage
from api.vm.utils import get_owners
from gui.forms import SerializerForm
from vms.models import Iso


class DcIsoForm(SerializerForm):
    """
    Create or remove DC<->Iso link by calling dc_iso.
    """
    _api_call = dc_iso

    name = forms.ChoiceField(label=_('ISO Image'), required=True,
                             widget=forms.Select(attrs={'class': 'input-select2 disable_created2 narrow'}))

    def __init__(self, request, isos, *args, **kwargs):
        super(DcIsoForm, self).__init__(request, None, *args, **kwargs)
        self.fields['name'].choices = isos.values_list('name', 'alias')

    def _final_data(self, data=None):
        return {}


class AdminIsoForm(SerializerForm):
    """
    Create, update or delete iso image by calling iso_manage.
    """
    _api_call = iso_manage

    dc_bound = forms.BooleanField(label=_('DC-bound?'), required=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    name = forms.CharField(label=_('Name'), max_length=32, required=True,
                           help_text=_('ISO image file name (including file extension).'),
                           widget=forms.TextInput(attrs={'class': 'input-transparent narrow disable_created',
                                                         'required': 'required', 'pattern': '[A-Za-z0-9._-]+'}))
    alias = forms.CharField(label=_('Alias'), required=True, max_length=32,
                            widget=forms.TextInput(attrs={'class': 'input-transparent narrow', 'required': 'required'}))
    owner = forms.ChoiceField(label=_('Owner'), required=False,
                              widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    access = forms.TypedChoiceField(label=_('Access'), required=False, coerce=int, choices=Iso.ACCESS,
                                    widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    ostype = forms.TypedChoiceField(label=_('OS Type'), required=False, coerce=int, empty_value=None,
                                    choices=(('', _('(none)')),) + Iso.OSTYPE,
                                    widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    desc = forms.CharField(label=_('Description'), max_length=128, required=False,
                           widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))

    def __init__(self, request, iso, *args, **kwargs):
        super(AdminIsoForm, self).__init__(request, iso, *args, **kwargs)
        self.fields['owner'].choices = get_owners(request).values_list('username', 'username')

        if not request.user.is_staff:
            self.fields['dc_bound'].widget.attrs['disabled'] = 'disabled'

    def _initial_data(self, request, obj):
        return obj.web_data

    def _final_data(self, data=None):
        data = super(AdminIsoForm, self)._final_data(data=data)

        if self.action == 'create':  # Add dc parameter when doing POST (required by api.db.utils.get_virt_object)
            data['dc'] = self._request.dc.name

        return data
