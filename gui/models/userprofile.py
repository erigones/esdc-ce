from django.utils.translation import LANGUAGE_SESSION_KEY, ugettext_lazy as _
from django.utils.six import iteritems
from django.db import models
from django.conf import settings
from timezone_field import TimeZoneField
# noinspection PyProtectedMember
from phonenumbers.data import _COUNTRY_CODE_TO_REGION_CODE

import os
import pytz

from gui.countries import COUNTRIES
from gui.models.user import User


def _tel_prefix_item(prefix):
    prefix = '+%d' % prefix
    return prefix, prefix


class UserProfile(models.Model):
    """
    User profile. Extends User object.
    """
    UNKNOWN = 0
    PERSONAL = 1
    COMPANY = 2
    USERTYPES = (
        (UNKNOWN, _('Unknown account')),
        (COMPANY, _('Company account')),
        (PERSONAL, _('Personal account')),
    )
    COUNTRIES = COUNTRIES
    TIMEZONES = tuple((pytz.timezone(tz), _(tz)) for tz in pytz.common_timezones)
    PHONE_PREFIXES = tuple(_tel_prefix_item(prefix) for prefix, val in iteritems(_COUNTRY_CODE_TO_REGION_CODE))

    # PK = FK = user
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
    # Other fields here
    tos_acceptation = models.BooleanField(_('Terms of Service'), default=False)
    # email is in user model
    email_token = models.CharField(_('Email verification token'), max_length=32, blank=True)
    email_verified = models.BooleanField(_('Email verified'), default=False)
    email2 = models.EmailField(_('Billing Email'), max_length=254, blank=True)
    email2_token = models.CharField(_('Billing Email verification token'), max_length=32, blank=True)
    email2_verified = models.BooleanField(_('Billing Email verified'), default=False)
    phone = models.CharField(_('Phone'), max_length=32, blank=True)
    phone_token = models.CharField(_('Phone verification token'), max_length=32, blank=True)
    phone_verified = models.BooleanField(_('Phone verified'), default=False)
    phone2 = models.CharField(_('Billing Phone'), max_length=32, blank=True)
    phone2_token = models.CharField(_('Billing Phone verification token'), max_length=32, blank=True)
    phone2_verified = models.BooleanField(_('Billing Phone verified'), default=False)
    newsletter_tech = models.BooleanField(_('Technical newsletter'), default=True)
    newsletter_buss = models.BooleanField(_('Business newsletter'), default=True)
    usertype = models.PositiveSmallIntegerField(_('Account type'), choices=USERTYPES, default=UNKNOWN)
    language = models.CharField(_('Language'), max_length=10, choices=settings.LANGUAGES,
                                default=settings.LANGUAGES[0][0])
    timezone = TimeZoneField(verbose_name=_('Time zone'), choices=TIMEZONES, default=settings.PROFILE_TIME_ZONE_DEFAULT)
    currency = models.CharField(_('Currency'), max_length=6, choices=settings.CURRENCY,
                                default=settings.CURRENCY_DEFAULT)
    # Common address details
    title = models.CharField(_('Title'), max_length=16, blank=True)
    # first_name is in user model
    middle_name = models.CharField(_('Middle name'), max_length=32, blank=True)
    # last_name is in user model
    website = models.CharField(_('Website'), max_length=255, blank=True)
    jabber = models.EmailField(_('Jabber'), max_length=255, blank=True)
    street_1 = models.CharField(_('Street address'), max_length=255, blank=True)
    street2_1 = models.CharField(_('Street address'), max_length=255, blank=True)
    city = models.CharField(_('City'), max_length=255, blank=True)
    postcode = models.CharField(_('ZIP/Postal Code'), max_length=12, blank=True)
    state = models.CharField(_('State/Province/Region'), max_length=128, blank=True)
    country = models.CharField(_('Country'), max_length=2, choices=COUNTRIES, default='SK')
    different_billing = models.BooleanField(_('Use different billing address'), default=False)
    street_2 = models.CharField(_('Street address'), max_length=255, blank=True)
    street2_2 = models.CharField(_('Street address'), max_length=255, blank=True)
    city2 = models.CharField(_('City'), max_length=255, blank=True)
    postcode2 = models.CharField(_('ZIP/Postal Code'), max_length=12, blank=True)
    state2 = models.CharField(_('State/Province/Region'), max_length=128, blank=True)
    country2 = models.CharField(_('Country'), max_length=2, choices=COUNTRIES, blank=True)
    # Company details
    company = models.CharField(_('Company'), max_length=255, blank=True)
    companyid = models.CharField(_('Company ID'), max_length=64, blank=True)
    taxid = models.CharField(_('TAX ID'), max_length=64, blank=True)
    vatid = models.CharField(_('VAT ID'), max_length=64, blank=True)
    bankid = models.CharField(_('Bank Account Number'), max_length=255, blank=True)

    alerting_phone = models.CharField(_('Phone'), max_length=32, blank=True)
    alerting_email = models.EmailField(_('Email address'), max_length=255, blank=True)
    alerting_jabber = models.EmailField(_('Jabber'), max_length=255, blank=True)

    class Meta:
        app_label = 'gui'
        verbose_name = _('User profile')
        verbose_name_plural = _('User profiles')

    def __unicode__(self):
        return '%s' % (self.user,)

    @property
    def first_name(self):
        return self.user.first_name

    @property
    def last_name(self):
        return self.user.last_name

    @property
    def email(self):
        return self.user.email

    @property
    def billing_email(self):
        if self.different_billing and self.email2:
            return self.email2
        return self.email

    @property
    def billing_phone(self):
        if self.different_billing and self.phone2:
            return self.phone2
        return self.phone

    @property
    def billing_address(self):
        if self.different_billing and self.street2_1 and self.postcode2 and self.city2 and self.country2:
            return {
                'street': self.street_2,
                'street2': self.street2_1,
                'postcode': self.postcode2,
                'city': self.city2,
                'state': self.state2,
                'country': self.country2
            }

        return {
            'street': self.street_1,
            'street2': self.street2_1,
            'postcode': self.postcode,
            'city': self.city,
            'state': self.state,
            'country': self.country
        }

    def is_ok(self):
        from vms.models import DefaultDc
        dc1_settings = DefaultDc().settings
        # TOS acceptation, verified email/phone and usertype is required _only_ if registration is enabled
        # Using global REGISTRATION_ENABLED, because TOS acceptation and field validation
        # must be required in each DC (even if the DC has registration disabled)
        return (
            self.user.email and (
                not dc1_settings.REGISTRATION_ENABLED or
                self.email_verified and
                (not dc1_settings.TOS_LINK or self.tos_acceptation) and
                (not (dc1_settings.PROFILE_PHONE_REQUIRED or dc1_settings.SMS_REGISTRATION_ENABLED)
                 or self.phone and self.phone_verified) and
                # A company user account also requires a valid company ID
                (self.usertype == self.PERSONAL or (self.usertype == self.COMPANY and self.companyid))
            )
        )

    @staticmethod
    def is_phone_required():
        from vms.models import DefaultDc
        dc1_settings = DefaultDc().settings
        return dc1_settings.PROFILE_PHONE_REQUIRED or dc1_settings.SMS_REGISTRATION_ENABLED

    @staticmethod
    def must_phone_be_verified():
        from vms.models import DefaultDc
        return DefaultDc().settings.SMS_REGISTRATION_ENABLED  # dc1_settings

    @staticmethod
    def generate_token(size=12):
        """
        Return random token.
        """
        return str(os.urandom(size).encode('hex'))

    def activate_locale(self, request):
        """
        Save language and timezone settings from profile into session.
        The settings are read by django middleware.
        """
        request.session[LANGUAGE_SESSION_KEY] = str(self.language)
        request.session[settings.TIMEZONE_SESSION_KEY] = str(self.timezone)
