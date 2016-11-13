from api.decorators import api_view, request_data_defaultdc, setting_required
from api.permissions import IsAnyDcDnsAdmin
from api.dns.record.api_views import RecordView

__all__ = ('dns_record_list', 'dns_record')


@api_view(('GET', 'POST', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcDnsAdmin,))  # IsAnyDcDnsAdmin does not do any checks; it sets request.dcs
@setting_required('DNS_ENABLED')
def dns_record_list(request, name, data=None):
    """
    List (:http:get:`GET </dns/domain/(name)/record>`) all DNS records which belong to a DNS domain.

    .. http:get:: /dns/domain/(name)/record

        :DC-bound?:
            * |dc-yes| - ``domain.dc_bound=true``
            * |dc-no| - ``domain.dc_bound=false``
        :Permissions:
            * |DnsAdmin| or |DomainOwner|
        :Asynchronous?:
            * |async-no|
        :arg data.full: Return list of objects with all record details (default: false)
        :type data.full: boolean
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``id``, ``name``, ``type``, ``ttl``, \
``disabled``, ``changed`` (default: ``id``)
        :type data.order_by: string
        :status 200: SUCCESS
        :status 403: Forbidden
    """
    if request.method == 'POST':
        return dns_record(request, name, 0, data=data)
    return RecordView(request, name, None, data).response(many=True)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@request_data_defaultdc(permissions=(IsAnyDcDnsAdmin,))  # IsAnyDcDnsAdmin does not do any checks; it sets request.dcs
@setting_required('DNS_ENABLED')
def dns_record(request, name, record_id, data=None):
    """
    Show (:http:get:`GET </dns/domain/(name)/record/(record_id)>`),
    create (:http:post:`POST </dns/domain/(name)/record>`,
    update (:http:put:`PUT </dns/domain/(name)/record/(record_id)>`) or
    delete (:http:delete:`DELETE </dns/domain/(name)/record/(record_id)>`)
    a DNS record.

    .. http:get:: /dns/domain/(name)/record/(record_id)

        :DC-bound?:
            * |dc-yes| - ``domain.dc_bound=true``
            * |dc-no| - ``domain.dc_bound=false``
        :Permissions:
            * |DnsAdmin| or |DomainOwner|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Domain name
        :type name: string
        :arg record_id: **required** - DNS record ID
        :type record_id: integer
        :status 200: SUCCESS
        :status 403: Forbidden
        :status 404: Domain not found / Record not found

    .. http:post:: /dns/domain/(name)/record

        :DC-bound?:
            * |dc-yes| - ``domain.dc_bound=true``
            * |dc-no| - ``domain.dc_bound=false``
        :Permissions:
            * |DnsAdmin| or |DomainOwner|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Domain name
        :type name: string
        :arg data.name: **required** - The name of the DNS record - the full URI the DNS server should pick up on
        :type data.name: string
        :arg data.type: **required** - DNS record type (one of: A, AAAA, CERT, CNAME, HINFO, KEY, LOC, MX, NAPTR, \
NS, PTR, RP, SOA, SPF, SSHFP, SRV, TLSA, TXT)
        :type data.type: string
        :arg data.content: **required** - DNS record content - the answer of the DNS query
        :type data.content: string
        :arg data.ttl: How long (seconds) the DNS client is allowed to remember this record (default: 3600)
        :type data.ttl: integer
        :arg data.prio: Priority used by some record types (default: 0)
        :type data.prio: integer
        :arg data.disabled: If set to true, this record is hidden from DNS clients (default: false)
        :type data.disabled: boolean
        :status 201: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Domain not found
        :status 406: Record already exists

    .. http:put:: /dns/domain/(name)/record/(record_id)

        :DC-bound?:
            * |dc-yes| - ``domain.dc_bound=true``
            * |dc-no| - ``domain.dc_bound=false``
        :Permissions:
            * |DnsAdmin| or |DomainOwner|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Domain name
        :type name: string
        :arg record_id: **required** - DNS record ID
        :type record_id: integer
        :arg data.name: The name of the DNS record - the full URI the DNS server should pick up on
        :type data.name: string
        :arg data.type: DNS record type (one of: A, AAAA, CERT, CNAME, HINFO, KEY, LOC, MX, NAPTR, NS, PTR, RP, \
SOA, SPF, SSHFP, SRV, TLSA, TXT)
        :type data.type: string
        :arg data.content: DNS record content - the answer of the DNS query
        :type data.content: string
        :arg data.ttl: How long (seconds) the DNS client is allowed to remember this record
        :type data.ttl: integer
        :arg data.prio: Priority used by some record types
        :type data.prio: integer
        :arg data.disabled: If set to true, this record is hidden from DNS clients
        :type data.disabled: boolean
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Domain not found / Record not found

    .. http:delete:: /dns/domain/(name)/record/(record_id)

        :DC-bound?:
            * |dc-yes| - ``domain.dc_bound=true``
            * |dc-no| - ``domain.dc_bound=false``
        :Permissions:
            * |DnsAdmin| or |DomainOwner|
        :Asynchronous?:
            * |async-no|
        :arg name: **required** - Domain name
        :type name: string
        :arg record_id: **required** - DNS record ID
        :type record_id: integer
        :status 200: SUCCESS
        :status 400: FAILURE
        :status 403: Forbidden
        :status 404: Domain not found / Record not found

    """
    return RecordView(request, name, record_id, data).response()
