from api.decorators import api_view, request_data_defaultdc, setting_required
from api.permissions import IsSuperAdminOrReadOnly, IsAnyDcDnsAdmin
from api.dns.domain.api_views import DomainView

__all__ = ('dns_domain_list', 'dns_domain')


@api_view(('GET',))
@request_data_defaultdc(permissions=(IsSuperAdminOrReadOnly, IsAnyDcDnsAdmin))  # IsAnyDcDnsAdmin does not do any checks
@setting_required('DNS_ENABLED')                                                # it just sets request.dcs
def dns_domain_list(request, data=None):
    """
    List (:http:get:`GET </dns/domain>`) all DNS domains.

    .. http:get:: /dns/domain

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |DnsAdmin| or |DomainOwner|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with all domain details (default: false)
        :type data.full: boolean
        :arg data.extended: Return list of objects with extended domain details (default: false)
        :type data.extended: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``name``, ``created`` (default: ``name``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    return DomainView(request, None, data).get(many=True)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data_defaultdc(permissions=(IsSuperAdminOrReadOnly, IsAnyDcDnsAdmin))  # IsAnyDcDnsAdmin does not do any checks
@setting_required('DNS_ENABLED')                                                # it just sets request.dcs
def dns_domain(request, name, data=None):
    """
    Show (:http:get:`GET </dns/domain/(name)>`), create (:http:post:`POST </dns/domain/(name)>`,
    update (:http:put:`PUT </dns/domain/(name)>`) or delete (:http:delete:`DELETE </dns/domain/(name)>`)
    a DNS domain.

    .. http:get:: /dns/domain/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |DnsAdmin| or |DomainOwner|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Domain name
        :type name: string
        :arg data.extended: Display extended domain details (default: false)
        :type data.extended: boolean
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Domain not found

    .. http:post:: /dns/domain/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Domain name
        :type name: string
        :arg data.access: Access type (1 - Public, 3 - Private) (default: 3)
        :type data.access: integer
        :arg data.owner: User that owns the domain (default: logged in user)
        :type data.owner: string
        :arg data.type: PowerDNS domain type which determines how records are replicated. One of MASTER, NATIVE. \
When set to MASTER, PowerDNS will send NOTIFY messages after zone changes to all hosts specified in NS record for \
given domain. When set to NATIVE, PowerDNS will use only internal database replication between master DNS \
server and slave DNS servers. (default: MASTER)
        :type data.type: string
        :arg data.tsig_keys: Comma separated list of TSIG keys that will be allowed to do zone transfer query for \
this domain. Format: "key-type:key-name:secret,key-type:key-name2:secret2"; Example: "hmac-sha256:mykey:aabbcc..". \
(default: empty)
        :type data.tsig_keys: string
        :arg data.desc: Domain description
        :type data.desc: string
        :arg data.dc_bound: Whether the domain is bound to a datacenter (requires |SuperAdmin| permission) \
(default: true)
        :type data.dc_bound: boolean
        :arg data.dc: Name of the datacenter the domain will be attached to (**required** if DC-bound)
        :type data.dc: string
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 406: Domain already exists

    .. http:put:: /dns/domain/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Domain name
        :type name: string
        :arg data.access: Access type (1 - Public, 3 - Private)
        :type data.access: integer
        :arg data.type: PowerDNS domain type which determines how records are replicated. One of MASTER, NATIVE. \
When set to MASTER, PowerDNS will send NOTIFY messages after zone changes to all hosts specified in NS record for \
given domain. When set to NATIVE, PowerDNS will use only internal database replication between master DNS \
server and slave DNS servers. (default: MASTER)
        :type data.type: string
        :arg data.owner: User that owns the domain
        :type data.owner: string
        :arg data.tsig_keys: Comma separated list of TSIG keys that will be allowed to do zone transfer query for \
this domain. Format: "key-type:key-name:secret,key-type:key-name2:secret2"; Example: "hmac-sha256:mykey:aabbcc..". \
(default: empty)
        :type data.tsig_keys: string
        :arg data.desc: Domain description
        :type data.desc: string
        :arg data.dc_bound: Whether the domain is bound to a datacenter (requires |SuperAdmin| permission)
        :type data.dc_bound: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Domain not found

    .. http:delete:: /dns/domain/(name)

        :DC-bound?:
            * |dc-yes| - ``dc_bound=true``
            * |dc-no| - ``dc_bound=false``
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Domain name
        :type name: string
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Domain not found
        :status 417: Default VM domain cannot be deleted

    """
    return DomainView(request, name, data).response()
