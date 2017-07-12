from api.decorators import api_view, request_data_defaultdc
from api.permissions import IsAnyDcUserAdminOrProfileOwner
from api.accounts.user.profile.api_views import UserProfileView

__all__ = ('userprofile_manage',)


@api_view(('GET', 'PUT'))
@request_data_defaultdc(permissions=(IsAnyDcUserAdminOrProfileOwner,))
def userprofile_manage(request, username, data=None):
    """
    Show (:http:get:`GET </accounts/user/(username)/profile>`) or
    edit (:http:put:`PUT </accounts/user/(username)/profile>`) user profile details.

    .. http:get:: /accounts/user/(username)/profile

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |ProfileOwner|
            * |UserAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg username: **required** - Username
        :type username: string

        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: User not found

    .. http:put:: /accounts/user/(username)/profile

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |ProfileOwner|
            * |UserAdmin| - ``dc_bound=true``
            * |SuperAdmin| - ``dc_bound=false``
        :Asynchronous?:
            * |async-no|
        :arg username: **required** - Username
        :type username: string
        :arg data.tos_acceptation: TOS acceptation
        :type data.tos_acceptation: boolean
        :arg data.email: Primary user email (valid email address)
        :type data.email: string
        :arg data.email_verified: Email verification check
        :type data.email_verified: boolean
        :arg data.email2: Secondary email (generally used for billing purposes, valid email address)
        :type data.email2: string
        :arg data.phone: Phone number (in international format +xx yyy yyyy yyyy, valid phone number)
        :type data.phone: string
        :arg data.phone_verified: Phone verification check
        :type data.phone_verified: boolean
        :arg data.phone2: Secondary phone number (Generally used for billing purposes, in international format \
+xx yyy yyyy yyyy, valid phone number)
        :type data.phone2: string
        :arg data.newsletter_tech: User willing to receive technical newsletters
        :type data.newsletter_tech: boolean
        :arg data.newsletter_buss: User willing to receive business newsletters
        :type data.newsletter_buss: boolean
        :arg data.usertype: Account type (available: 0: Unknown account type, 1: Personal account, 2: Company account)
        :type data.usertype: integer
        :arg data.language: Default language used after user login (available: en, sk)
        :type data.language: string
        :arg data.timezone: Default timezone used for user
        :type data.timezone: string
        :arg data.currency: Default currency used in billing (available: EUR)
        :type data.currency: string
        :arg data.title: User title
        :type data.title: string
        :arg data.first_name: User first name
        :type data.first_name: string
        :arg data.middle_name: User middle name
        :type data.middle_name: string
        :arg data.last_name: User last name
        :type data.last_name: string
        :arg data.website: User website
        :type data.website: string
        :arg data.jabber: User jabber account (valid email address format)
        :type data.jabber: string
        :arg data.street_1: Street (primary address)
        :type data.street_1: string
        :arg data.street2_1: Street - second line (primary address)
        :type data.street2_1: string
        :arg data.city: City (primary address)
        :type data.city: string
        :arg data.postcode: Postal code (primary address)
        :type data.postcode: string
        :arg data.state: State (primary address)
        :type data.state: string
        :arg data.country: Country code (primary address) (e.g: SK, GB, US...)
        :type data.country: string
        :arg data.different_billing: Use different address for billing?
        :type data.different_billing: boolean
        :arg data.street2_1: Street (secondary/billing address)
        :type data.street2_1: string
        :arg data.street2_2: Street - second line (secondary/billing address)
        :type data.street2_2: string
        :arg data.city2: City (secondary/billing address)
        :type data.city2: string
        :arg data.postcode2: Postal code (secondary/billing address)
        :type data.postcode2: string
        :arg data.state2: State (secondary/billing address)
        :type data.state2: string
        :arg data.country2: Country code (secondary/billing address)
        :type data.country2: string
        :arg data.company: Company name
        :type data.company: string
        :arg data.companyid: Company ID
        :type data.companyid: string
        :arg data.taxid: Company Tax ID
        :type data.taxid: string
        :arg data.vatid: Company VAT ID
        :type data.vatid: string
        :arg data.bankid: Bank Account Number
        :type data.bankid: string
        :arg data.alerting_email: Email address used for alerting purposes (valid email address format)
        :type data.alerting_email: string
        :arg data.alerting_phone: Phone number used for alerting purposes
        :type data.alerting_phone: string
        :arg data.alerting_jabber: Jabber account used for alerting purposes (valid email address format)
        :type data.alerting_jabber: string

        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: User not found
    """
    return UserProfileView(request, username, data).response()
