from api.utils.db import get_object
from vms.models import Node


def get_node(request, hostname, attrs=None, where=None, exists_ok=True, noexists_fail=True, sr=(), pr=(),
             dc=False, api=True, extra=None, annotate=None):
    """Call get_object for Node model identified by hostname.
    This function should be called by staff users or DC admins only."""
    if attrs is None:
        attrs = {}

    if not request.user.is_staff:  # DC admin
        attrs['dc'] = request.dc

    if dc:
        attrs['dc'] = dc

    attrs['hostname'] = hostname

    if api:
        return get_object(request, Node, attrs, where=where, exists_ok=exists_ok, noexists_fail=noexists_fail, sr=sr,
                          pr=pr, extra=extra, annotate=annotate)

    if sr:
        qs = Node.objects.select_related(*sr)
    else:
        qs = Node.objects

    if where:
        return qs.filter(where).get(**attrs)
    else:
        return qs.get(**attrs)


def get_nodes(request, sr=(), pr=(), order_by=('hostname',), annotate=None, extra=None, **kwargs):
    """Return queryset of nodes available for current admin"""
    if not request.user.is_staff:  # DC admin
        kwargs['dc'] = request.dc

    if sr:
        qs = Node.objects.select_related(*sr)
    else:
        qs = Node.objects

    if pr:
        qs = qs.prefetch_related(*pr)

    if annotate:
        qs = qs.annotate(**annotate)

    if extra:
        qs = qs.extra(**extra)

    if kwargs:
        return qs.filter(**kwargs).order_by(*order_by)

    return qs.order_by(*order_by)
