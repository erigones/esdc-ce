from logging import getLogger

from vms.models import Snapshot, DefaultDc
from que import TG_DC_UNBOUND
from que.tasks import execute
from api.api_views import APIView
from api.utils.request import get_dummy_request
from api.exceptions import NodeIsNotOperational
from api.task.response import SuccessTaskResponse, TaskResponse, FailureTaskResponse
from api.node.messages import LOG_NS_SNAPS_SYNC
from api.vm.snapshot.serializers import SnapshotSerializer
from api.vm.snapshot.utils import filter_disk_id, filter_snap_type, filter_snap_define

logger = getLogger(__name__)


class NodeVmSnapshotList(APIView):
    """
    api.node.snapshot.views.node_vm_snapshot_list
    """
    LOCK = 'node_vm_snapshot_list %s'
    dc_bound = False
    order_by_default = ('-id',)
    order_by_fields = ('name', 'disk_id', 'size')
    order_by_field_map = {'created': 'id', 'hostname': 'vm__hostname'}

    def __init__(self, request, ns, data):
        super(NodeVmSnapshotList, self).__init__(request)
        self.data = data
        self.ns = ns

    @staticmethod
    def filter_snapshot_vm(query_filter, data):
        """Validate server hostname and update dictionary used for queryset filtering"""
        if 'vm' in data:
            if data['vm']:
                query_filter['vm__hostname'] = data['vm']

        return query_filter

    def get(self):
        request, data = self.request, self.data

        # Prepare filter dict
        snap_filter = {'zpool': self.ns}
        self.filter_snapshot_vm(snap_filter, data)
        filter_disk_id(None, snap_filter, data)
        filter_snap_type(snap_filter, data)
        filter_snap_define(snap_filter, data)

        # TODO: check indexes
        snapqs = Snapshot.objects.select_related('vm', 'define', 'zpool').filter(**snap_filter).order_by(*self.order_by)

        if self.full or self.extended:
            if snapqs:
                res = SnapshotSerializer(request, snapqs, many=True).data
            else:
                res = []
        else:
            res = list(snapqs.values_list('name', flat=True))

        return SuccessTaskResponse(request, res, dc_bound=False)

    def put(self, internal=False):
        """Sync snapshots in DB with snapshots on compute node storage and update snapshot status and size."""
        request, ns = self.request, self.ns
        node = ns.node

        # Prepare task data
        apiview = {
            'view': 'node_vm_snapshot_list',
            'method': request.method,
            'hostname': node.hostname,
            'zpool': ns.zpool,
        }
        meta = {
            'output': {'returncode': 'returncode', 'stdout': 'data', 'stderr': 'message'},
            'msg': LOG_NS_SNAPS_SYNC,
            'nodestorage_id': ns.id,
            'apiview': apiview,
            'internal': internal,
        }
        cmd = 'esnapshot list "%s"' % ns.zpool
        lock = self.LOCK % ns.id
        callback = ('api.node.snapshot.tasks.node_vm_snapshot_sync_cb', {'nodestorage_id': ns.id})

        if node.status != node.ONLINE:
            raise NodeIsNotOperational

        # Run task
        tid, err = execute(request, ns.storage.owner.id, cmd, tg=TG_DC_UNBOUND, meta=meta, lock=lock, callback=callback,
                           queue=node.fast_queue, check_user_tasks=not internal)

        if internal:
            return tid, err

        if err:
            return FailureTaskResponse(request, err, dc_bound=False)
        else:
            return TaskResponse(request, tid, msg=LOG_NS_SNAPS_SYNC, obj=ns, api_view=apiview, data=self.data)

    @classmethod
    def sync(cls, node):
        """Run put() for all node storages on compute node"""
        request = get_dummy_request(DefaultDc(), method='PUT', system_user=True)
        data = {}
        result = {}

        for ns in node.nodestorage_set.all():
            view = cls(request, ns, data)
            result[ns] = tid, err = view.put(internal=True)

            if err:
                logger.error('Failed to create node_vm_snapshot_sync task for %s@%s. Error: %s',
                             ns.zpool, node.hostname, err)
            else:
                logger.info('Created node_vm_snapshot_sync task %s for %s@%s', tid, ns.zpool, node.hostname)

        return result
