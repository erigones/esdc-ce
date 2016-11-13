from django import forms
from django.utils.translation import ugettext_lazy as _

from api.accounts.group.views import group_manage
from api.accounts.user.utils import ExcludeInternalUsers
from api.dc.group.views import dc_group
from gui.forms import SerializerForm
from gui.models import Permission, User


class DcGroupForm(SerializerForm):
    """
    Create or remove DC<->Iso link by calling dc_iso.
    """
    _api_call = dc_group

    name = forms.ChoiceField(label=_('User group'), required=True,
                             widget=forms.Select(attrs={'class': 'input-select2 disable_created2 narrow'}))

    def __init__(self, request, groups, *args, **kwargs):
        super(DcGroupForm, self).__init__(request, None, *args, **kwargs)
        self.fields['name'].choices = groups.values_list('name', 'alias')

    def _final_data(self, data=None):
        return {}


class AdminGroupForm(SerializerForm):
    """
    Create, update or delete user group by calling group_manage.
    """
    _api_call = group_manage

    dc_bound = forms.BooleanField(label=_('DC-bound?'), required=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    name = forms.CharField(label=_('Name'), max_length=80, required=True,
                           widget=forms.TextInput(attrs={'class': 'input-transparent narrow disable_created',
                                                         'required': 'required', 'pattern': '[A-Za-z0-9\._-]+'}))
    alias = forms.CharField(label=_('Alias'), required=True, max_length=80,
                            widget=forms.TextInput(attrs={'class': 'input-transparent narrow', 'required': 'required'}))
    users = forms.MultipleChoiceField(label=_('Users'), required=False,
                                      widget=forms.SelectMultiple(attrs={'class': 'narrow input-select2 tags-select2'}))
    permissions = forms.MultipleChoiceField(label=_('Permissions'), required=False,
                                            widget=forms.SelectMultiple(attrs={'class': 'narrow input-select2 '
                                                                                        'tags-select2'}))

    def __init__(self, request, group, *args, **kwargs):
        super(AdminGroupForm, self).__init__(request, group, *args, **kwargs)
        self.fields['users'].choices = User.objects.filter(ExcludeInternalUsers).values_list('username', 'username')
        self.fields['permissions'].choices = Permission.objects.all().values_list('name', 'alias')

        if not request.user.is_staff:
            self.fields['dc_bound'].widget.attrs['disabled'] = 'disabled'

    def _initial_data(self, request, obj):
        return obj.web_data

    def _final_data(self, data=None):
        data = super(AdminGroupForm, self)._final_data(data=data)

        if self.action == 'create':  # Add dc parameter when doing POST (required by api.db.utils.get_virt_object)
            data['dc'] = self._request.dc.name

        return data
