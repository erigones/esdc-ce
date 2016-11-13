from django.db.models import Count

from api.dc.utils import get_dcs
from api.dc.base.serializers import ExtendedDcSerializer


def get_dcs_extended(request, sr=('owner',), pr=None):
    """
    Return queryset of all DCs including extended stats; used by dc_list view.
    """
    annotation = {
        'vms': Count('vm', distinct=True),
        'dcnodes': Count('dcnode', distinct=True),
    }
    extra = {'select': ExtendedDcSerializer.extra_select}

    return get_dcs(request, sr=sr, pr=pr, annotate=annotation, extra=extra)
