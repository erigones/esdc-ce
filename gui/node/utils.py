from django.http import Http404
from django.db.models import Count, Sum

from vms.models import Node
from gui.utils import get_order_by, get_pager
from api.node.utils import get_nodes as api_get_nodes, get_node as api_get_node
from api.node.base.serializers import ExtendedNodeSerializer
from api.vm.backup.vm_backup_list import VmBackupList


get_nodes = api_get_nodes


def get_nodes_extended(request):
    """
    Return extended nodes query set; used by node_list
    """
    return api_get_nodes(request, annotate={'vms': Count('vm')}, extra={'select': ExtendedNodeSerializer.extra_select})


def get_node(request, hostname, **kwargs):
    """
    Get Node object or raise 404.
    """
    try:
        return api_get_node(request, hostname, api=False, **kwargs)
    except Node.DoesNotExist:
        raise Http404


def get_node_backups(request, queryset):
    """
    Return dict with backups attribute.
    """
    user_order_by, order_by = get_order_by(request, api_view=VmBackupList,
                                           db_default=('-id',), user_default=('-created',))
    bkps = get_pager(request, queryset.order_by(*order_by), per_page=50)

    return {
        'order_by': user_order_by,
        'pager': bkps,
        'backups': bkps,
        'backups_count': bkps.paginator.count,
        'backups_size': queryset.exclude(size__isnull=True).aggregate(Sum('size')).get('size__sum'),
    }
