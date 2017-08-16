import re
from logging import getLogger
from django.conf import settings
from django import forms
from django.db.models import Q
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm as _PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.translation import ugettext_lazy as _
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from api.email import sendmail
from gui.models import User, UserProfile
from gui.widgets import EmailInput, TelPrefixInput, clean_international_phonenumber
from gui.accounts.utils import send_sms, generate_key, set_attempts_to_cache

logger = getLogger(__name__)

UNUSABLE_PASSWORD = '!'


class LoginForm(AuthenticationForm):
    """
    A form that is used for authenticating user into system.
    """
    def __init__(self, request, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        self.request = request
        self.fields['username'].label = _('username or email')
        self.fields['username'].widget = EmailInput(
            attrs={'class': 'input-transparent', 'placeholder': _('Username or Email'), 'required': 'required'},
        )
        self.fields['password'].widget = forms.PasswordInput(
            render_value=False,
            attrs={'class': 'input-transparent', 'placeholder': _('Password'), 'required': 'required'},
        )

    def clean_username(self):
        return self.cleaned_data['username'].lower()

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            self.user_cache = authenticate(username=username, password=password)
            key, timeout = generate_key(self.request, username, 'login')
            attempts, timeout = set_attempts_to_cache(key, timeout)

            if self.user_cache is None or attempts > 3 or (
               settings.SECURITY_OWASP_AT_002 and not self.user_cache.is_active):
                if attempts > 3:
                    logger.warning('Ignoring login request from user "%s", %s attempts lock will expire in %s seconds.',
                                   username, attempts, timeout)
                    if not settings.SECURITY_OWASP_AT_002:
                        self.error_messages['invalid_login'] = _('You made %(attempts)s wrong login attempts, all '
                                                                 'further attempts will be ignored for %(timeout)s '
                                                                 'seconds.') % {'attempts': attempts,
                                                                                'timeout': timeout}

                raise forms.ValidationError(self.error_messages['invalid_login'], code='invalid_login',
                                            params={'username': self.username_field.verbose_name})
            elif not self.user_cache.is_active:
                raise forms.ValidationError(self.error_messages['inactive'], code='inactive')

        return self.cleaned_data


class ForgotForm(_PasswordResetForm):
    """
    A form that lets a user change,set his/her password without entering the old password.
    """
    def __init__(self, request, *args, **kwargs):
        super(ForgotForm, self).__init__(*args, **kwargs)
        self.request = request
        self.fields['email'].widget.attrs = {
            'class': 'input-transparent',
            'placeholder': _('Your email address'),
            'required': 'required'
        }
        self.fields['email'].help_text = _('You will receive an email with instructions on how to reset your password.')

    # noinspection PyArgumentList,PyUnusedLocal
    def clean_email(self, *args, **kwargs):
        """
        We never raise an ValidationError, because user Enumeration and Guessable User Account OWASP-AT-002.
        Change this behaviour with settings.SECURITY_OWASP_AT_002.
        """
        email = self.cleaned_data['email']
        users = User.objects.filter(email__iexact=email, is_active=True).exclude(password=UNUSABLE_PASSWORD)
        self.users_cache = []

        # Check for valid user:
        if users:
            key, timeout = generate_key(self.request, email, 'forgot')
            attempts, timeout = set_attempts_to_cache(key, timeout)
            # Don't allow a password reset if user is trying more than 2 time in calculated timeout
            if attempts > 2:
                logger.warning('Ignoring password reset request from user "%s", %s attempts lock will expire in %s '
                               'seconds.', email, attempts, timeout)
                if settings.SECURITY_OWASP_AT_002:
                    return email
                else:
                    raise forms.ValidationError(_('You have requested password reset %(attempts)s times. '
                                                  'All further attempts will be ignored for %(timeout)s '
                                                  'seconds.') % {'attempts': attempts, 'timeout': timeout})
        else:
            logger.warning('Ignoring password reset request from invalid user "%s"', email)
            if settings.SECURITY_OWASP_AT_002:
                return email
            else:
                raise forms.ValidationError(_("That email address doesn't have an associated user account. Are you "
                                              "sure you've registered?"))

        # A valid user is part of a self.users_cache list used in save()
        # noinspection PyAttributeOutsideInit
        self.users_cache = users

        return email

    def save(self, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.html',
             use_https=False, token_generator=default_token_generator,
             **kwargs):
        # Complete override, because we have to use our sendmail()
        for user in self.users_cache:
            # Update verification token
            profile = user.userprofile
            profile.email_token = token_generator.make_token(user)
            profile.save()
            sendmail(user, subject_template_name, email_template_name, extra_context={
                'user': user,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': profile.email_token,
                'protocol': use_https and 'https' or 'http',
            })


class PasswordResetForm(object):
    """
    Dummy "password reset" form used by django.contrib.auth.forms.password_reset_confirm.
    """
    # noinspection PyUnusedLocal
    def __init__(self, user, data=None):
        self.user = user

    def is_valid(self):
        return self.user.is_active

    def save(self):
        password = User.objects.make_random_password(length=7)
        self.user.set_password(password)
        self.user.save()
        msg = _('Your password at %(site_name)s has been reset to: %(password)s') % {
            'site_name': self.user.current_dc.settings.SITE_NAME,
            'password': password, }
        send_sms(self.user.userprofile.phone, msg)

        return None


class RegisterForm(forms.ModelForm):
    """
    User details registration form, for basic user data (Django users table)
    """
    validate_against_users = True
    email_help_text = _('You will receive an email to activate your account.')

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'email': EmailInput(attrs={'class': 'input-transparent',
                                       'placeholder': _('Email address'),
                                       'required': 'required',
                                       'maxlength': 254}),
            'first_name': forms.TextInput(attrs={'class': 'input-transparent',
                                                 'placeholder': _('First name'),
                                                 'required': 'required',
                                                 'maxlength': 30}),
            'last_name': forms.TextInput(attrs={'class': 'input-transparent',
                                                'placeholder': _('Last name'),
                                                'required': 'required',
                                                'maxlength': 30}),
        }

    def __init__(self, *args, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        self.fields['email'].help_text = self.email_help_text

    # noinspection PyUnusedLocal
    def clean_email(self, *args, **kwargs):
        email = self.cleaned_data['email']

        if self.validate_against_users:
            if User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)):
                raise forms.ValidationError(_('This email address is already in use. Please supply a different email '
                                              'address.'))

        email_clean_regex = re.compile("^[A-Za-z0-9@.+_-]+$")

        if email_clean_regex.match(email) is None:
            raise forms.ValidationError(_('Sorry. Your email address did not pass the validity test.'))

        return email


class UserProfileRegisterForm(forms.ModelForm):
    """
    User profile registration form, for extended data collected about user (gui users table)
    """
    include_company = False
    include_tos = bool(settings.TOS_LINK)
    include_others = True
    phone_help_text = _('You will receive a text message (SMS) with password.')

    class Meta:
        model = UserProfile
        fields = ['phone', 'tos_acceptation', 'company', 'companyid', 'country', 'timezone', 'language']
        widgets = {
            'phone': TelPrefixInput(attrs={
                'class': 'input-transparent',
                'placeholder': _('Phone'),
                'required': 'required',
                'maxlength': 32
            }),
            'tos_acceptation': forms.CheckboxInput(attrs={
                'class': 'normal-check',
                'placeholder': _('TOS Confirmation'),
                # 'required': 'required'
                # Do not use the HTML5 required attribute
                # Browser support on checkboxes lacks behind
            }),
            'company': forms.TextInput(attrs={
                'class': 'input-transparent',
                'placeholder': _('Company'),
                'required': 'required',
                'maxlength': 255
            }),
            'companyid': forms.TextInput(attrs={
                'class': 'input-transparent',
                'placeholder': _('Company ID'),
                'required': 'required',
                'maxlength': 64
            }),
            'country': forms.HiddenInput(),
            'timezone': forms.HiddenInput(),
            'language': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super(UserProfileRegisterForm, self).__init__(*args, **kwargs)
        self.fields['phone'].required = True
        self.fields['phone'].help_text = self.phone_help_text

        if not self.include_tos:
            del(self.fields['tos_acceptation'])

        if not self.include_company:
            del(self.fields['company'], self.fields['companyid'])
        else:
            self.fields['company'].required = True
            self.fields['companyid'].required = True

        if not self.include_others:
            del(self.fields['country'], self.fields['timezone'], self.fields['language'])

    def clean_phone(self):
        return clean_international_phonenumber(self.cleaned_data['phone'])

    def clean_tos_acceptation(self):
        data = self.cleaned_data['tos_acceptation']
        if not data:
            raise forms.ValidationError(_('In order to use this service, you have to accept the Terms of Service.'))
        return data

    def save(self, *args, **kwargs):
        # a "hack" to get the actual instance alive
        instance = kwargs.pop('instance', None)
        if instance:
            self.instance = forms.models.construct_instance(self, instance, self._meta.fields, self._meta.exclude)

        return super(UserProfileRegisterForm, self).save(*args, **kwargs)
