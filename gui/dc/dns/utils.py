from django.shortcuts import Http404
from django.db.models import Q

from pdns.models import Domain


def get_domain(request, name):
    """
    get_domain() suitable for GUI.
    """
    if request.user.is_staff:
        qs = Domain.objects
    else:
        qs = Domain.objects.filter(Q(user=request.user.id) | Q(dc_bound=request.dc.id))

    try:
        domain = qs.get(name=name)
    except Domain.DoesNotExist:
        raise Http404

    return domain
