from logging import getLogger

from django.utils.translation import ugettext_noop as _

from api import status
from api.api_views import APIView
from api.exceptions import PreconditionRequired
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.utils.db import get_object
from api.dc.node.utils import get_dc_nodes
from api.dc.node.serializers import DcNodeSerializer, ExtendedDcNodeSerializer
from api.dc.messages import LOG_NODE_ATTACH, LOG_NODE_UPDATE, LOG_NODE_DETACH
from vms.models import Node, DcNode, NodeStorage

logger = getLogger(__name__)


class DcNodeView(APIView):
    serializer = DcNodeSerializer
    order_by_default = ('node__hostname',)
    order_by_field_map = {'hostname': 'node__hostname'}

    def __init__(self, request, hostname, data):
        super(DcNodeView, self).__init__(request)
        self.data = data
        self.hostname = hostname

        if hostname:
            self.node = get_object(request, Node, {'hostname': hostname}, exists_ok=True, noexists_fail=True)
            self.dcnode = get_object(request, DcNode, {'dc': request.dc, 'node': self.node}, sr=('dc', 'node'))
        else:
            self.node = Node
            self.dcnode = get_dc_nodes(request, prefetch_vms_count=self.extended, order_by=self.order_by)

    def get(self, many=False):
        if self.extended:
            self.serializer = ExtendedDcNodeSerializer

        if many or not self.hostname:
            if self.full or self.extended:

                if self.dcnode:
                    res = self.serializer(self.request, self.dcnode, many=True).data
                else:
                    res = []
            else:
                res = list(self.dcnode.values_list('node__hostname', flat=True))
        else:
            if self.extended:
                # noinspection PyUnresolvedReferences
                self.dcnode.vms = self.node.vm_set.filter(dc=self.request.dc).count()
                # noinspection PyUnresolvedReferences
                self.dcnode.real_vms = self.node.vm_set.filter(dc=self.request.dc, slavevm__isnull=True).count()
            res = self.serializer(self.request, self.dcnode).data

        return SuccessTaskResponse(self.request, res)

    def post(self):
        node, dcnode = self.node, self.dcnode
        request, data = self.request, self.data

        # Set defaults for Shared strategy (default)
        try:
            strategy = int(data.get('strategy', DcNode.SHARED))
        except ValueError:
            strategy = DcNode.SHARED
        if strategy == DcNode.SHARED:
            dcnode.cpu = dcnode.ram = dcnode.disk = 0  # Value doesn't matter => will be set in save/update_resources
            data.pop('cpu', None)
            data.pop('ram', None)
            data.pop('disk', None)

        # Used in GUI
        try:
            add_storage = int(data.pop('add_storage', DcNode.NS_ATTACH_NONE))
        except ValueError:
            add_storage = DcNode.NS_ATTACH_NONE

        ser = DcNodeSerializer(request, dcnode, data=data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=node)

        ser.object.save(update_resources=False)
        DcNode.update_all(node=node)
        ser.reload()

        if add_storage:
            from api.utils.views import call_api_view
            from api.dc.storage.views import dc_storage
            ns = NodeStorage.objects.filter(node=node)

            if add_storage != DcNode.NS_ATTACH_ALL:
                ns = ns.filter(storage__access=add_storage)

            for zpool in ns.values_list('zpool', flat=True):
                try:
                    zpool_node = '%s@%s' % (zpool, node.hostname)
                    res = call_api_view(request, 'POST', dc_storage, zpool_node, data={}, log_response=True)

                    if res.status_code == 201:
                        logger.info('POST dc_storage(%s) was successful: %s', zpool_node, res.data)
                    else:
                        logger.error('POST dc_storage(%s) failed: %s: %s', zpool_node, res.status_code, res.data)
                except Exception as ex:
                    logger.exception(ex)

        return SuccessTaskResponse(request, ser.data, status=status.HTTP_201_CREATED, obj=node,
                                   detail_dict=ser.detail_dict(), msg=LOG_NODE_ATTACH)

    def put(self):
        node, dcnode = self.node, self.dcnode

        ser = DcNodeSerializer(self.request, dcnode, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=node)

        ser.object.save(update_resources=False)
        DcNode.update_all(node=node)
        ser.reload()

        return SuccessTaskResponse(self.request, ser.data, obj=node, detail_dict=ser.detail_dict(), msg=LOG_NODE_UPDATE)

    def delete(self):
        node, dcnode = self.node, self.dcnode

        if dcnode.dc.vm_set.filter(node=node).exists():
            raise PreconditionRequired(_('Node has VMs in datacenter'))

        if dcnode.dc.backup_set.filter(node=node).exists():
            raise PreconditionRequired(_('Node has VM backups in datacenter'))

        ser = DcNodeSerializer(self.request, dcnode)
        ser.object.delete()
        DcNode.update_all(node=node)
        # noinspection PyStatementEffect
        ser.data

        return SuccessTaskResponse(self.request, None, obj=node, detail_dict=ser.detail_dict(), msg=LOG_NODE_DETACH)
