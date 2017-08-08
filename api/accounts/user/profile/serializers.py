from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from api.serializers import InstanceSerializer, NoPermissionToModify
from api.fields import EmailField, BooleanField, ChoiceField, SafeCharField, IntegerChoiceField
from gui.accounts.utils import send_sms
from gui.models import UserProfile
from gui.widgets import clean_international_phonenumber
from gui.countries import COUNTRIES


class UserProfileSerializer(InstanceSerializer):
    """
    gui.models.user
    """
    _model_ = UserProfile
    _update_fields_ = ('tos_acceptation', 'email', 'email_verified', 'email2', 'phone', 'phone_verified', 'phone2',
                       'newsletter_tech', 'newsletter_buss', 'usertype', 'language', 'timezone', 'currency', 'title',
                       'first_name', 'middle_name', 'last_name', 'website', 'jabber', 'street_1', 'street2_1', 'city',
                       'postcode', 'state', 'country', 'different_billing', 'street_2', 'street2_2', 'city2',
                       'postcode2', 'state2', 'country2', 'company', 'companyid', 'taxid', 'vatid', 'bankid',
                       'alerting_email', 'alerting_phone', 'alerting_jabber')
    _default_fields_ = ('username', 'tos_acceptation', 'email_verified', 'email2', 'phone_verified', 'phone2',
                        'newsletter_tech', 'newsletter_buss', 'usertype', 'language', 'timezone', 'currency', 'title',
                        'middle_name', 'website', 'jabber', 'street_1', 'street2_1', 'city', 'postcode', 'state',
                        'country', 'different_billing', 'street_2', 'street2_2', 'city2', 'postcode2', 'state2',
                        'country2', 'company', 'companyid', 'taxid', 'vatid', 'bankid',
                        'alerting_email', 'alerting_phone', 'alerting_jabber')
    _blank_fields_ = ('email_token', 'email2', 'email2_token', 'phone_token', 'phone2', 'phone2_token', 'title',
                      'middle_name', 'website', 'jabber', 'street_1', 'street2_1', 'city', 'postcode', 'state',
                      'street_2', 'street2_2', 'city2', 'postcode2', 'state2', 'country2', 'company', 'companyid',
                      'taxid', 'vatid', 'bankid', 'alerting_email', 'alerting_phone', 'alerting_jabber')

    username = SafeCharField(source='user.username', label=_('Username'), read_only=True)
    tos_acceptation = BooleanField(label=_('Terms of Service'), help_text=_('TOS acceptation check.'))
    email = SafeCharField(source='user.email', label=_('Email address'))
    email_verified = BooleanField(label=_('Email verified'), help_text=_('Email verification check.'))
    email2 = EmailField(label=_('Billing Email'), max_length=254, required=False)
    phone = SafeCharField(label=_('Phone'), max_length=32)
    phone_verified = BooleanField(label=_('Phone verified'), help_text=_('Phone verification check.'))
    phone2 = SafeCharField(label=_('Billing Phone'), max_length=32, required=False)
    newsletter_tech = BooleanField(label=_('Technical newsletter'),)
    newsletter_buss = BooleanField(label=_('Business newsletter'),)
    usertype = IntegerChoiceField(label=_('Account type'), choices=UserProfile.USERTYPES, default=UserProfile.UNKNOWN,
                                  required=True)
    language = ChoiceField(label=_('Language'), choices=settings.LANGUAGES, default=settings.LANGUAGES[0][0])
    timezone = ChoiceField(label=_('Time zone'), choices=UserProfile.TIMEZONES,
                           default=settings.PROFILE_TIME_ZONE_DEFAULT)
    currency = ChoiceField(label=_('Currency'), choices=settings.CURRENCY, default=settings.CURRENCY_DEFAULT)
    # Common address details
    title = SafeCharField(label=_('Title'), max_length=16, required=False)
    first_name = SafeCharField(source='user.first_name')
    middle_name = SafeCharField(label=_('Middle name'), max_length=32, required=False)
    last_name = SafeCharField(source='user.last_name')
    website = SafeCharField(label=_('Website'), max_length=255, required=False)
    jabber = EmailField(label=_('Jabber'), max_length=255, required=False)
    street_1 = SafeCharField(label=_('Street address'), max_length=255, required=False)
    street2_1 = SafeCharField(label=_('Street address 2'), max_length=255, required=False,
                              help_text=_('Optional, use in case your address contains multiple names.'))
    city = SafeCharField(label=_('City'), max_length=255, required=False)
    postcode = SafeCharField(label=_('ZIP/Postal Code'), max_length=12, required=False)
    state = SafeCharField(label=_('State/Province/Region'), max_length=128, required=False)
    country = ChoiceField(label=_('Country'), choices=COUNTRIES, default=settings.PROFILE_COUNTRY_CODE_DEFAULT)
    different_billing = BooleanField(label=_('Use different billing address'),)
    street_2 = SafeCharField(label=_('Street address'), max_length=255, required=False)
    street2_2 = SafeCharField(label=_('Street address 2'), max_length=255, required=False,
                              help_text=_('Optional, use in case your address contains multiple names.'))
    city2 = SafeCharField(label=_('City'), max_length=255, required=False)
    postcode2 = SafeCharField(label=_('ZIP/Postal Code'), max_length=12, required=False)
    state2 = SafeCharField(label=_('State/Province/Region'), max_length=128, required=False)
    country2 = ChoiceField(label=_('Country'), choices=COUNTRIES, default=settings.PROFILE_COUNTRY_CODE_DEFAULT,
                           required=False)
    # Company details
    company = SafeCharField(label=_('Company'), max_length=255, required=False)
    companyid = SafeCharField(label=_('Company ID'), max_length=64, required=False)
    taxid = SafeCharField(label=_('TAX ID'), max_length=64, required=False)
    vatid = SafeCharField(label=_('VAT ID'), max_length=64, required=False)
    bankid = SafeCharField(label=_('Bank Account Number'), max_length=255, required=False)
    old_phone = None

    alerting_phone = SafeCharField(label=_('Phone'), max_length=32, required=False)
    alerting_jabber = EmailField(label=_('Jabber'), max_length=255, required=False)
    alerting_email = EmailField(label=_('Email'), max_length=255, required=False)

    # noinspection PyProtectedMember
    def save(self, **kwargs):
        profile = self.object

        # Changing a user phone makes the phone not verified
        # (unless request.user is not part of the staff or registration is disabled)
        if self.old_phone and not self.request.user.is_staff and settings.REGISTRATION_ENABLED:
            profile.phone_verified = False
            profile.phone_token = profile.generate_token(3)

            msg = _('Please confirm your new phone number at %(site_link)s with this activation code: %(token)s') % {
                'site_link': profile.user.current_dc.settings.SITE_LINK,
                'token': profile.phone_token}
            send_sms(profile.phone, msg)

        profile.save()

        # We cannot change active language settings for other user than ourself
        if self.request.user == profile.user:
            profile.activate_locale(self.request)

    def validate_phone(self, attrs, source):
        try:
            value = clean_international_phonenumber(attrs[source])
        except KeyError:
            pass
        else:
            if self.object.phone == value:
                return attrs
            else:
                # Store old phone number for later so we know we have to send text message
                self.old_phone = self.object.phone
            # Store formatted phone number
            attrs[source] = value

        return attrs

    # noinspection PyMethodMayBeStatic
    def validate_phone2(self, attrs, source):
        try:
            value = clean_international_phonenumber(attrs[source])
        except KeyError:
            pass
        else:
            # Store formatted phone number
            attrs[source] = value

        return attrs

    # noinspection PyMethodMayBeStatic
    def validate_alerting_phone(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if value:
                # Store formatted phone number
                attrs[source] = clean_international_phonenumber(value)

        return attrs

    def validate_email_verified(self, attrs, source):
        try:
            attrs[source]
        except KeyError:
            pass
        else:
            if not self.request.user.is_staff:
                raise NoPermissionToModify()

        return attrs

    def validate_phone_verified(self, attrs, source):
        try:
            attrs[source]
        except KeyError:
            pass
        else:
            if not self.request.user.is_staff:
                raise NoPermissionToModify()

        return attrs
