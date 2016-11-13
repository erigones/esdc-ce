from vms.models import NodeStorage
from api.utils.db import get_object
from api.node.utils import get_node


def output_extended(request):
    if request.method == 'GET' and request.query_params.get('extended', False):
        return {
            'snapshot_count': '''SELECT COUNT(*) FROM "vms_snapshot" WHERE
    "vms_nodestorage"."id" = "vms_snapshot"."zpool_id"''',
            'backup_count': '''SELECT COUNT(*) FROM "vms_backup" WHERE
    "vms_nodestorage"."id" = "vms_backup"."zpool_id"''',
            'image_count': '''SELECT COUNT(*) FROM "vms_nodestorage_images" WHERE
    "vms_nodestorage"."id" = "vms_nodestorage_images"."nodestorage_id"''',
        }
    return None


def get_node_storages(request, hostname, sr=('storage', 'node', 'storage__owner'), pr=('dc',), order_by=('zpool',)):
    """Return queryset of NodeStorage objects. Used only by staff users!"""
    node = get_node(request, hostname, exists_ok=True, noexists_fail=True)
    qs = node.nodestorage_set.select_related(*sr).order_by(*order_by)
    extended = output_extended(request)

    if extended:
        qs = qs.prefetch_related(*pr).extra(extended)

    return qs


def get_node_storage(request, hostname, zpool, sr=('node', 'storage', 'storage__owner')):
    """Return NodeStorage object. Used only by staff users!"""
    node = get_node(request, hostname, exists_ok=True, noexists_fail=True)
    extended = output_extended(request)

    if extended:
        extra = {'select': extended}
        pr = ('dc',)
    else:
        pr = ()
        extra = None

    return get_object(request, NodeStorage, {'node': node, 'zpool': zpool}, sr=sr, pr=pr, extra=extra)
