from logging import getLogger

from django.db.models import Q

from api.exceptions import PermissionDenied
from api.dc.utils import get_dc
from api.utils.db import get_object
from pdns.models import Domain
from vms.models import Dc, DomainDc

logger = getLogger(__name__)


def get_domain(request, name, attrs=None, fetch_dc=False, data=None, count_records=False, **kwargs):
    """Return Domain object according to name. SuperAdmins have access to all domains and
    users can access only domain which they own. This function also acts as IsDomainOwner permission."""
    user = request.user

    if attrs is None:
        attrs = {}

    if user.is_staff:
        dom_filter = None
    else:
        dom_filter = Q(user=user.id)

        if request.dcs:
            # noinspection PyAugmentAssignment
            dom_filter = dom_filter | Q(dc_bound__in=[dc.id for dc in request.dcs])

    if count_records:
        # noinspection SqlDialectInspection,SqlNoDataSourceInspection
        kwargs['extra'] = {
            'select': {'records': 'SELECT COUNT(*) FROM "records" WHERE "records"."domain_id" = "domains"."id"'}
        }

    attrs['name'] = name.lower()  # The domain name must be always lowercased (DB requirement)
    domain = get_object(request, Domain, attrs, where=dom_filter, **kwargs)

    if domain.new:
        domain.dc_bound = get_dc(request, data.get('dc', request.dc.name)).id

    if not (user.is_staff or domain.user == user.id):
        # request.dcs is brought by IsAnyDcPermission
        if not (domain.dc_bound and Dc.objects.get_by_id(domain.dc_bound) in request.dcs):
            raise PermissionDenied  # only DC-bound objects are visible by non-superadmin users

    if domain.dc_bound:  # Change DC according to domain.dc_bound flag
        if request.dc.id != domain.dc_bound:
            request.dc = Dc.objects.get_by_id(domain.dc_bound)  # Warning: Changing request.dc

            if not user.is_staff:
                request.dc_user_permissions = request.dc.get_user_permissions(user)

            logger.info('"%s %s" user="%s" _changed_ dc="%s" permissions=%s', request.method, request.path,
                        user.username, request.dc.name, request.dc_user_permissions)

    if fetch_dc:
        if domain.id:
            domain.dc = list(Dc.objects.filter(domaindc__domain_id=domain.id))
        else:
            domain.dc = []

    return domain


def prefetch_domain_owner(domain_qs):
    """Prefetch owner (from domain.user field) for a Domain queryset"""
    user_ids = set([domain.user for domain in domain_qs if domain.user])
    users = {user.id: user for user in Domain.get_user_model().objects.filter(id__in=user_ids)}

    for domain in domain_qs:
        domain._owner = users.get(domain.user, Domain.NoOwner())

    return domain_qs


def prefetch_domain_dcs(domain_qs):
    """Prefetch DCs (from DomainDc table) for a Domain queryset"""
    domain_ids = [domain.id for domain in domain_qs]
    domain_dcs = {}

    for domdc in DomainDc.objects.select_related('dc').filter(domain_id__in=domain_ids):
        try:
            domain_dcs[domdc.domain_id].append(domdc.dc)
        except KeyError:
            domain_dcs[domdc.domain_id] = [domdc.dc]

    for domain in domain_qs:
        domain.dc = domain_dcs.get(domain.id, [])

    return domain_qs


def get_domains(request, prefetch_owner=False, prefetch_dc=False, count_records=False, order_by=('name',), **kwargs):
    """Return queryset of Domains. SuperAdmins see all domains and user can see only domain they own."""
    if request.user.is_staff:
        qs = Domain.objects.order_by(*order_by).exclude(access=Domain.INTERNAL)
    else:
        dom_filter = Q(user=request.user.id)

        if request.dcs:
            # noinspection PyAugmentAssignment
            dom_filter = dom_filter | Q(dc_bound__in=[dc.id for dc in request.dcs])

        qs = Domain.objects.order_by(*order_by).filter(dom_filter).exclude(access=Domain.INTERNAL)

    if kwargs:
        qs = qs.filter(**kwargs)

    if count_records:
        # noinspection SqlDialectInspection,SqlNoDataSourceInspection
        qs = qs.extra({'records': 'SELECT COUNT(*) FROM "records" WHERE "records"."domain_id" = "domains"."id"'})

    if prefetch_dc:
        qs = prefetch_domain_dcs(qs)

    if prefetch_owner:
        return prefetch_domain_owner(qs)
    else:
        return qs


def reverse_domain_from_network(ip_network):
    """Create reverse DNS zone name from network address (ipaddress.IPv4Network)"""
    prefixlen = ip_network.prefixlen

    if prefixlen % 8:
        return ip_network.reverse_pointer  # classless
    else:
        return ip_network.network_address.reverse_pointer[(4 - (prefixlen / 8)) * 2:]  # classful
