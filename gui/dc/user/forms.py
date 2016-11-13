from logging import getLogger

from django import forms
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from frozendict import frozendict

from api.utils.views import call_api_view
from api.accounts.user.base.views import user_manage
from api.accounts.user.profile.views import userprofile_manage
from api.accounts.user.profile.serializers import UserProfileSerializer
from gui.forms import SerializerForm
from gui.models import Role, UserProfile
from gui.widgets import EmailInput, URLInput, TelPrefixInput
from gui.profile.forms import PasswordForm

logger = getLogger(__name__)


class AdminUserForm(SerializerForm):
    """
    Create, update or delete user by calling user_manage.
    """
    _api_call = user_manage

    dc_bound = forms.BooleanField(label=_('DC-bound?'), required=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    username = forms.CharField(label=_('Username'), max_length=80, required=True,
                               widget=forms.TextInput(attrs={'class': 'uneditable-input', 'required': 'required',
                                                             'pattern': '[A-Za-z0-9\@\._-]+'}))
    groups = forms.MultipleChoiceField(label=_('User groups'), required=False,
                                       widget=forms.SelectMultiple(attrs={'class': 'narrow input-select2 '
                                                                                   'tags-select2'}))
    is_super_admin = forms.BooleanField(label=_('SuperAdmin status'), required=False,
                                        widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    is_active = forms.BooleanField(label=_('Active'), required=False,
                                   widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    api_access = forms.BooleanField(label=_('Access to API'), required=False,
                                    widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))

    def __init__(self, request, user, *args, **kwargs):
        super(AdminUserForm, self).__init__(request, user, *args, **kwargs)

        if request.user.is_staff:
            self.fields['groups'].choices = Role.objects.all().values_list('name', 'alias')
        else:
            self.fields['dc_bound'].widget.attrs['disabled'] = 'disabled'
            self.fields['is_super_admin'].widget.attrs['disabled'] = 'disabled'
            # UserAdmins should see only dc_bound groups, but unfortunately they have to additionally see groups
            # that are already assigned to users, they can modify
            group_filter = Q(dc_bound=request.dc) | Q(user__dc_bound=request.dc)
            self.fields['groups'].choices = Role.objects.distinct().filter(group_filter).values_list('name', 'alias')

    def _initial_data(self, request, obj):
        return obj.web_data

    def _final_data(self, data=None):
        data = super(AdminUserForm, self)._final_data(data=data)

        if data:
            # Add dc parameter when doing any request (required by validate_dc_bound() in UserSerializer)
            data['dc'] = self._request.dc.name

        return data


class AdminUserModalForm(AdminUserForm):
    """
    Create, update or delete user by calling user_manage.
    """
    first_name = forms.CharField(label=_('First name'), required=True, max_length=30,
                                 widget=forms.TextInput(attrs={'required': 'required'}))
    last_name = forms.CharField(label=_('Last name'), required=True, max_length=30,
                                widget=forms.TextInput(attrs={'required': 'required'}))
    email = forms.EmailField(label=_('Email address'), required=True, max_length=254,
                             widget=EmailInput(attrs={'required': 'required'}))

    password = forms.CharField(label=_('New password'), required=False, min_length=6, max_length=64,
                               widget=forms.PasswordInput(render_value=False))
    password2 = forms.CharField(label=_('Confirm password'), required=False, min_length=6, max_length=64,
                                widget=forms.PasswordInput(render_value=False))

    def __init__(self, request, user, *args, **kwargs):
        super(AdminUserModalForm, self).__init__(request, user, *args, **kwargs)
        # Fix CSS classes because the base Form is _not_ used in a modal window
        self.fields['username'].widget.attrs['class'] = 'input-transparent narrow disable_created'
        self.fields['first_name'].widget.attrs['class'] = 'input-transparent narrow'
        self.fields['last_name'].widget.attrs['class'] = 'input-transparent narrow'
        self.fields['email'].widget.attrs['class'] = 'input-transparent narrow'
        self.fields['password'].widget.attrs['class'] = 'input-transparent narrow'
        self.fields['password2'].widget.attrs['class'] = 'input-transparent narrow'

    def clean(self):
        cleaned_data = super(AdminUserModalForm, self).clean()
        password = cleaned_data.get('password')
        password2 = cleaned_data.get('password2')

        if password and not password2:
            self._errors['password2'] = self.error_class([_('You must confirm your password.')])
            del cleaned_data['password']
            del cleaned_data['password2']

        elif password and password2 and password != password2:
            self._errors['password'] = self.error_class([_('Your passwords do not match.')])
            self._errors['password2'] = self.error_class([_('Your passwords do not match.')])
            del cleaned_data['password']
            del cleaned_data['password2']

        return cleaned_data

    def _final_data(self, data=None):
        data = super(AdminUserModalForm, self)._final_data(data=data)

        if 'password' in data and data['password'] == '':
            del(data['password'])

        if 'password2' in data and data['password2'] == '':
            del(data['password2'])

        return data


COMPANY_ACCOUNT_ATTRS = {'data-usertype': UserProfile.COMPANY}


class AdminUserProfileForm(SerializerForm):
    """
    Update user profile by calling userprofile_manage.
    """
    _api_call = userprofile_manage
    _serializer = UserProfileSerializer
    _custom_widgets = frozendict({
        'website': URLInput,
        'phone': TelPrefixInput,
        'phone2': TelPrefixInput,
        'usertype': forms.RadioSelect,
    })
    _custom_widget_attrs = frozendict({
        'website': {'maxlength': 255},
        'phone': {'required': 'required', 'maxlength': 32},
        'phone2': {'maxlength': 32},
        'usertype': {
            'required': 'required',
            'class': 'normal-radio'
        },
        'company': COMPANY_ACCOUNT_ATTRS,
        'companyid': COMPANY_ACCOUNT_ATTRS,
        'taxid': COMPANY_ACCOUNT_ATTRS,
        'vatid': COMPANY_ACCOUNT_ATTRS,
    })
    _field_text_class = ''

    def _input_data(self):
        """Overloaded because if user doesn't check different_billing we don't want to send
        address2 data for validation"""
        data = super(AdminUserProfileForm, self)._input_data()
        if not data['different_billing']:
            for index in ('phone2', 'email2', 'street_2', 'street2_2', 'postcode2', 'city2', 'state2', 'country2'):
                if index in data:
                    del(data[index])
        return data

    def clean(self):
        cleaned_data = super(AdminUserProfileForm, self).clean()
        phone = cleaned_data.get('phone')
        cleaned_data['phone'] = phone.replace(' ', '')

        phone2 = cleaned_data.get('phone2')
        cleaned_data['phone2'] = phone2.replace(' ', '')

        return cleaned_data


class AdminChangePasswordForm(PasswordForm):
    """
    Password form used to change user password.
    """
    def __init__(self, *args, **kwargs):
        super(AdminChangePasswordForm, self).__init__(*args, **kwargs)
        self.fields['password1'].label = _('New password')
        self.fields['password1'].widget.attrs['placeholder'] = ''
        self.fields['password2'].label = _('Confirm new password')
        self.fields['password2'].widget.attrs['placeholder'] = ''

    # noinspection PyMethodOverriding
    def save(self, request):
        args = self.user.username
        data = {'password': self.cleaned_data['password1']}
        logger.info('Calling API view PUT user_manage(%s, data=%s) by user %s in DC %s',
                    args, {'password': '***'}, request.user, request.dc)
        res = call_api_view(request, 'PUT', user_manage, args, data=data)
        return res.status_code
