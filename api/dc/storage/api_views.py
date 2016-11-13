from django.utils.translation import ugettext_noop as _

from api import status
from api.api_views import APIView
from api.exceptions import ObjectNotFound, PreconditionRequired, ObjectAlreadyExists
from api.task.response import SuccessTaskResponse
from api.utils.db import get_object
from api.dc.storage.serializers import DcNodeStorageSerializer, ExtendedDcNodeStorageSerializer
from api.dc.messages import LOG_STORAGE_ATTACH, LOG_STORAGE_DETACH
from vms.models import NodeStorage, DcNode


class DcStorageView(APIView):
    serializer = DcNodeStorageSerializer
    order_by_default = ('node__hostname', 'zpool')
    order_by_field_map = {'hostname': 'node__hostname', 'zpool': 'zpool'}

    def __init__(self, request, name, data):
        super(DcStorageView, self).__init__(request)
        self.data = data
        self.name = name
        dc = request.dc

        if name:
            try:
                zpool, hostname = name.split('@')
                if not (zpool and hostname):
                    raise ValueError
            except ValueError:
                raise ObjectNotFound(model=NodeStorage)

            attrs = {'node__hostname': hostname, 'zpool': zpool}

            if request.method != 'POST':
                attrs['dc'] = dc

            ns = get_object(request, NodeStorage, attrs, sr=('node', 'storage', 'storage__owner',),
                            exists_ok=True, noexists_fail=True)
            ns.set_dc(dc)

            try:  # Bug #chili-525 + checks if node is attached to Dc (must be!)
                ns.set_dc_node(DcNode.objects.get(node=ns.node, dc=dc))
            except DcNode.DoesNotExist:
                raise PreconditionRequired(_('Compute node is not available'))

        else:  # many
            ns = NodeStorage.objects.filter(dc=dc).order_by(*self.order_by)

            if self.full or self.extended:
                dc_nodes = {dn.node.hostname: dn for dn in DcNode.objects.select_related('node').filter(dc=request.dc)}
                ns = ns.select_related('node', 'storage', 'storage__owner')

                for i in ns:  # Bug #chili-525
                    i.set_dc_node(dc_nodes.get(i.node.hostname, None))
                    i.set_dc(dc)

        self.ns = ns

    def get(self, many=False):
        if self.extended:
            serializer = ExtendedDcNodeStorageSerializer
        else:
            serializer = self.serializer

        if many or not self.name:
            if self.full or self.extended:
                if self.ns:
                    # noinspection PyUnresolvedReferences
                    res = serializer(self.request, self.ns, many=True).data
                else:
                    res = []
            else:
                res = ['@'.join(i) for i in self.ns.values_list('zpool', 'node__hostname')]
        else:
            # noinspection PyUnresolvedReferences
            res = serializer(self.request, self.ns).data

        return SuccessTaskResponse(self.request, res)

    def post(self):
        ns, dc = self.ns, self.request.dc

        if ns.dc.filter(id=dc.id).exists():
            raise ObjectAlreadyExists(model=NodeStorage)

        ser = self.serializer(self.request, ns)
        ns.dc.add(dc)

        return SuccessTaskResponse(self.request, ser.data, obj=ns, status=status.HTTP_201_CREATED,
                                   detail_dict=ser.detail_dict(), msg=LOG_STORAGE_ATTACH)

    def delete(self):
        ns, dc = self.ns, self.request.dc

        for vm in dc.vm_set.filter(node=ns.node):
            if ns.zpool in vm.get_used_disk_pools():  # active + current
                raise PreconditionRequired(_('Storage is used by some VMs'))

        if dc.backup_set.filter(zpool=ns).exists():
            raise PreconditionRequired(_('Storage is used by some VM backups'))

        ser = self.serializer(self.request, ns)
        ns.dc.remove(dc)

        return SuccessTaskResponse(self.request, None, obj=ns, detail_dict=ser.detail_dict(), msg=LOG_STORAGE_DETACH)
