from logging import getLogger
from collections import OrderedDict

from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from gui.countries import COUNTRIES
from gui.models import UserProfile
from gui.widgets import EmailInput, URLInput, TelPrefixInput
from gui.forms import SerializerForm
from gui.utils import user_profile_company_only_form
from gui.profile.utils import get_user_serializer, get_userprofile_serializer
from api.accounts.user.base.views import user_manage
from api.accounts.user.profile.views import userprofile_manage
from api.accounts.user.sshkey.views import sshkey_manage
from api.utils.views import call_api_view

logger = getLogger(__name__)

REQUIRED = {'required': 'required'}


class UserForm(SerializerForm):
    """
    User form, used in profile for basic user data (Django users table)
    """
    _api_call = user_manage

    first_name = forms.CharField(label=_('First name'),
                                 required=True,
                                 widget=forms.TextInput(attrs={
                                     'required': 'required',
                                     'maxlength': 30}),
                                 )
    last_name = forms.CharField(label=_('Last name'),
                                required=True,
                                widget=forms.TextInput(attrs={
                                    'required': 'required',
                                    'maxlength': 30}),
                                )
    email = forms.EmailField(label=_('Email address'),
                             required=True,
                             widget=EmailInput(attrs={
                                 'required': 'required',
                                 'maxlength': 254}),
                             )

    def __init__(self, request, user, *args, **kwargs):
        super(UserForm, self).__init__(request, user, *args, **kwargs)

        # Whether to require email validation. Using global REGISTRATION_ENABLED, because the validation must be
        # performed in each DC (even if the DC has registration disabled).
        if not user.is_staff and settings.REGISTRATION_ENABLED:
            self.fields['email'].help_text = 'notverified'
            if user.userprofile.email_verified:
                self.fields['email'].help_text = _('WARNING: After changing the email address you will receive a email '
                                                   'to validate the new email address.')

    def _initial_data(self, request, obj):
        return get_user_serializer(request, obj)

    def save(self, action=None, args=()):
        status = super(UserForm, self).save(action, args)
        if status == 200 and self._obj.email != self.cleaned_data['email']:
            # Email has changed we need to show verify button
            self.fields['email'].help_text = 'notverified'

        return status


class UserProfileForm(SerializerForm):
    """
    User form, used in profile for basic user data (Django users table)
    """
    _api_call = userprofile_manage

    title = forms.CharField(label=_('Title'),
                            required=False,
                            widget=forms.TextInput(attrs={'maxlength': 16}),
                            )
    middle_name = forms.CharField(label=_('Middle name'),
                                  required=False,
                                  widget=forms.TextInput(attrs={'maxlength': 32}),
                                  )
    phone = forms.CharField(label=_('Phone'),
                            required=True,
                            widget=TelPrefixInput(attrs={
                                'required': 'required',
                                'maxlength': 32}),
                            )
    jabber = forms.CharField(label=_('Jabber'),
                             required=False,
                             widget=EmailInput(attrs={'maxlength': 255}),
                             )
    website = forms.CharField(label=_('Website'),
                              required=False,
                              widget=URLInput(attrs={'maxlength': 255}),
                              )
    tos_acceptation = forms.BooleanField(label=_('TOS Acceptation'),
                                         required=True,
                                         help_text=_('I accept the General Terms and Conditions.'),
                                         widget=forms.CheckboxInput(attrs={
                                             'required': 'required',
                                             'class': 'normal-check'}),
                                         )
    street_1 = forms.CharField(label=_('Street address'),
                               required=True,
                               widget=forms.TextInput(attrs={
                                   'required': 'required',
                                   'maxlength': 255}),
                               )
    street2_1 = forms.CharField(label=_('Street address 2'),
                                required=False,
                                help_text=_('Optional, use in case your address contains multiple names.'),
                                widget=forms.TextInput(attrs={
                                    'maxlength': 255}),
                                )
    postcode = forms.CharField(label=_('ZIP/Postal Code'),
                               required=True,
                               widget=forms.TextInput(attrs={
                                   'required': 'required',
                                   'maxlength': 12}),
                               )
    city = forms.CharField(label=_('City'),
                           required=True,
                           widget=forms.TextInput(attrs={
                               'required': 'required',
                               'maxlength': 255}),
                           )
    state = forms.CharField(label=_('State/Province/Region'),
                            required=False,
                            widget=forms.TextInput(attrs={
                                'maxlength': 128}),
                            )
    country = forms.ChoiceField(label=_('Country'),
                                required=True,
                                choices=COUNTRIES,
                                widget=forms.Select(),
                                )
    different_billing = forms.BooleanField(label=_('Use different billing address'),
                                           required=False,
                                           widget=forms.CheckboxInput(attrs={
                                               'class': 'normal-check'}),
                                           )
    phone2 = forms.CharField(label=_('Billing Phone'),
                             required=False,
                             widget=TelPrefixInput(attrs={
                                 'maxlength': 32}),
                             )
    email2 = forms.CharField(label=_('Billing Email'),
                             required=False,
                             widget=forms.TextInput(attrs={
                                 'maxlength': 254}),
                             )
    street_2 = forms.CharField(label=_('Street address'),
                               required=True,
                               widget=forms.TextInput(attrs={
                                   'required': 'required',
                                   'maxlength': 255}),
                               )
    street2_2 = forms.CharField(label=_('Street address 2'),
                                required=False,
                                help_text=_('Optional, use in case your address contains multiple names.'),
                                widget=forms.TextInput(attrs={
                                    'maxlength': 255}),
                                )
    postcode2 = forms.CharField(label=_('ZIP/Postal Code'),
                                required=True,
                                widget=forms.TextInput(attrs={
                                    'required': 'required',
                                    'maxlength': 12}),
                                )
    city2 = forms.CharField(label=_('City'),
                            required=True,
                            widget=forms.TextInput(attrs={
                                'required': 'required',
                                'maxlength': 255}),
                            )
    state2 = forms.CharField(label=_('State/Province/Region'),
                             required=False,
                             widget=forms.TextInput(attrs={
                                 'maxlength': 128}),
                             )
    country2 = forms.ChoiceField(label=_('Country'),
                                 required=True,
                                 choices=COUNTRIES,
                                 widget=forms.Select(),
                                 )
    company = forms.CharField(label=_('Company'),
                              required=True,
                              widget=forms.TextInput(attrs={
                                  'required': 'required',
                                  'data-usertype': '2',
                                  'maxlength': 255}),
                              )
    companyid = forms.CharField(label=_('Company ID'),
                                required=True,
                                widget=forms.TextInput(attrs={
                                    'data-usertype': '2',
                                    'maxlength': 64}),
                                )
    taxid = forms.CharField(label=_('TAX ID'),
                            required=False,
                            widget=forms.TextInput(attrs={
                                'data-usertype': '2',
                                'maxlength': 64}),
                            )
    vatid = forms.CharField(label=_('VAT ID'),
                            required=False,
                            widget=forms.TextInput(attrs={
                                'data-usertype': '2',
                                'maxlength': 64}),
                            )
    usertype = forms.TypedChoiceField(label=_('Account type'),
                                      coerce=int,
                                      required=True,
                                      choices=UserProfile.USERTYPES[1:],
                                      widget=forms.RadioSelect(attrs={
                                          'required': 'required',
                                          'class': 'normal-radio'}),
                                      )
    language = forms.ChoiceField(label=_('Language'),
                                 required=False,
                                 choices=settings.LANGUAGES,
                                 widget=forms.Select(),
                                 )
    timezone = forms.ChoiceField(label=_('Time zone'),
                                 required=False,
                                 choices=UserProfile.TIMEZONES,
                                 widget=forms.Select(),
                                 )
    newsletter_tech = forms.BooleanField(label=_('Technical newsletter'),
                                         required=False,
                                         widget=forms.CheckboxInput(attrs={
                                             'class': 'normal-check'}),
                                         )
    newsletter_buss = forms.BooleanField(label=_('Business newsletter'),
                                         required=False,
                                         widget=forms.CheckboxInput(attrs={
                                             'class': 'normal-check'}),
                                         )
    currency = forms.ChoiceField(label=_('Currency'),
                                 required=False,
                                 choices=settings.CURRENCY,
                                 widget=forms.Select(),
                                 )

    def __init__(self, request, profile, *args, **kwargs):
        super(UserProfileForm, self).__init__(request, profile, *args, **kwargs)

        # Display TOS acceptation checkbox if user did not accepted TOS and registration is enabled
        if (profile.user.is_staff or profile.tos_acceptation or
                not settings.REGISTRATION_ENABLED or not settings.TOS_LINK):
            del self.fields['tos_acceptation']

        if not profile.user.is_staff and user_profile_company_only_form(profile.user):
            self.fields['usertype'].choices = list(UserProfile.USERTYPES[1:2])

        # Using global REGISTRATION_ENABLED,
        # because the fields must be required in each DC (even if the DC has registration disabled)
        if not settings.REGISTRATION_ENABLED:
            self.fields['street_1'].required = False
            self.fields['postcode'].required = False
            self.fields['city'].required = False
            self.fields['country'].required = False
            self.fields['email2'].required = False
            self.fields['street_2'].required = False
            self.fields['postcode2'].required = False
            self.fields['city2'].required = False
            self.fields['country2'].required = False
            del self.fields['newsletter_tech']
            del self.fields['newsletter_buss']

        # Whether to require phone validation.
        if not profile.user.is_staff and settings.REGISTRATION_ENABLED:
            self.fields['phone'].help_text = 'notverified'
            if profile.phone_verified:
                self.fields['phone'].help_text = _('WARNING: After changing the phone number you will receive a text '
                                                   'message to validate the new phone number.')

        if request.method == 'POST':
            usertype = request.POST.get('usertype', profile.usertype)
            if str(usertype) == str(UserProfile.PERSONAL):
                self.fields['company'].required = False
                self.fields['companyid'].required = False
            if not request.POST.get('different_billing', False):
                # Secondary address is required only if user select he want to add it
                self.fields['email2'].required = False
                self.fields['street_2'].required = False
                self.fields['postcode2'].required = False
                self.fields['city2'].required = False
                self.fields['country2'].required = False

    def _input_data(self):
        """Overloaded because if user doesnt check different_billing we don't want to send
        address2 data for validation"""
        data = super(UserProfileForm, self)._input_data()
        if not data['different_billing']:
            for index in ('phone2', 'email2', 'street_2', 'street2_2', 'postcode2', 'city2', 'state2', 'country2'):
                if index in data:
                    del(data[index])
        return data

    def _initial_data(self, request, obj):
        return get_userprofile_serializer(request, obj)


class EmailActivationProfileForm(forms.Form):
    """
    User Profile form, which is displayed when email address is not verified.
    """
    email_token = forms.CharField(
        label=_('Email activation code'),
        max_length=24, required=True,
        widget=forms.TextInput(attrs={
            'required': 'required',  # HTML5 validation
            'class': 'input-transparent',
            'max_length': '16',
            'placeholder': _('Email activation code'),
        }))

    def __init__(self, token, *args, **kwargs):
        self.token = token
        super(EmailActivationProfileForm, self).__init__(*args, **kwargs)

    def clean_email_token(self):
        data = self.cleaned_data['email_token']
        if data != self.token:
            raise forms.ValidationError(_('Email activation code is invalid.'))

        return data


class PhoneActivationProfileForm(forms.Form):
    """
    User Profile form, which is displayed when phone number is not verified.
    """
    phone_token = forms.CharField(
        label=_('Phone activation code'),
        max_length=24, required=True,
        widget=forms.TextInput(attrs={
            'required': 'required',  # HTML5 validation
            'class': 'input-transparent',
            'maxlength': '16',
            'placeholder': _('Phone activation code'),
        }))

    def __init__(self, token, *args, **kwargs):
        self.token = token
        super(PhoneActivationProfileForm, self).__init__(*args, **kwargs)

    def clean_phone_token(self):
        data = self.cleaned_data['phone_token']
        if data != self.token:
            raise forms.ValidationError(_('Phone activation code is invalid.'))

        return data


class PasswordForm(forms.Form):
    """
    Password form used to set user password.
    """
    password1 = forms.CharField(
        label=_('Password'),
        required=True,
        min_length=6,
        widget=forms.PasswordInput(render_value=False, attrs={
            'class': 'input-transparent',
            'placeholder': _('Password'),
            'required': 'required',
        }),
    )
    password2 = forms.CharField(
        label=_('Confirm password'),
        required=True, min_length=6,
        widget=forms.PasswordInput(render_value=False, attrs={
            'class': 'input-transparent',
            'placeholder': _('Confirm password'),
            'required': 'required',
        }),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(PasswordForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(PasswordForm, self).clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if not password2:
            self._errors['password2'] = self.error_class([_('You must confirm your password.')])

        if password1 and password2 and password1 != password2:
            self._errors['password1'] = self.error_class([_('Your passwords do not match.')])
            self._errors['password2'] = self.error_class([_('Your passwords do not match.')])
            del cleaned_data['password1']
            del cleaned_data['password2']

        return cleaned_data

    def save(self, commit=True, user=None):
        if user:
            self.user = user
        self.user.set_password(self.cleaned_data['password1'])
        if commit:
            self.user.save()
        return self.user


class ChangePasswordForm(PasswordForm):
    """
    Password form used to change user password.
    """
    old_password = forms.CharField(
        label=_('Old password'),
        required=True,
        widget=forms.PasswordInput(render_value=False, attrs={
            'class': 'input-transparent',
            'required': 'required',
        }),
    )

    def __init__(self, *args, **kwargs):
        super(ChangePasswordForm, self).__init__(*args, **kwargs)
        self.fields['password1'].label = _('New password')
        self.fields['password1'].widget.attrs['placeholder'] = ''
        self.fields['password2'].label = _('Confirm new password')
        self.fields['password2'].widget.attrs['placeholder'] = ''

    def clean_old_password(self):
        old_password = self.cleaned_data['old_password']
        if not self.user.check_password(old_password):
            raise forms.ValidationError(_('Your old password was entered incorrectly.'))
        return old_password

    # noinspection PyMethodOverriding
    def save(self, request):
        args = self.user.username
        data = {'password': self.cleaned_data['password1']}
        logger.info('Calling API view PUT user_manage(%s, data=%s) by user %s in DC %s',
                    args, {'password': '***'}, request.user, request.dc)
        res = call_api_view(request, 'PUT', user_manage, args, data=data)
        return res.status_code


# Change order of password fields
ChangePasswordForm.base_fields = OrderedDict([
    (k, ChangePasswordForm.base_fields[k])
    for k in ('old_password', 'password1', 'password2')
])


class SSHKeyForm(SerializerForm):
    """
    Form used in profile for SSH public key add/update.
    """
    _api_call = sshkey_manage

    name = forms.CharField(label=_('Key title'),
                           required=True,
                           widget=forms.TextInput(attrs={
                               'class': 'input-transparent',
                               'required': 'required',
                               'maxlength': 64}),
                           )
    key = forms.CharField(label=_('Key'),
                          help_text=_('Public SSH key in OpenSSH format.'),
                          required=True,
                          widget=forms.Textarea(attrs={
                              'class': 'input-transparent small',
                              'required': 'required',
                              'rows': 5})
                          )
