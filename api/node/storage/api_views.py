from django.utils.translation import ugettext_noop as _
from django.db import IntegrityError, transaction

from vms.models import Storage
from api.status import HTTP_201_CREATED
from api.api_views import APIView
from api.exceptions import PreconditionRequired
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.node.storage.serializers import NodeStorageSerializer, ExtendedNodeStorageSerializer
from api.node.messages import LOG_NS_CREATE, LOG_NS_UPDATE, LOG_NS_DELETE


class NodeStorageView(APIView):
    dc_bound = False
    order_by_default = order_by_fields = ('zpool',)
    order_by_field_map = {'created': 'id'}

    @staticmethod
    def _get_zpool_vms(ns):
        return ({'hostname': vm.hostname, 'dc': vm.dc.name, 'disk': vm.get_disk_size(zpool=ns.zpool)}
                for vm in ns.node.vm_set.select_related('dc').all().order_by('hostname')
                if ns.zpool in vm.get_used_disk_pools())

    def get(self, ns, many=False):
        """Get node-storage"""
        if self.extended:
            ser_class = ExtendedNodeStorageSerializer

            if many:
                for _ns in ns:
                    _ns.vms = self._get_zpool_vms(_ns)
            else:
                ns.vms = self._get_zpool_vms(ns)
        else:
            ser_class = NodeStorageSerializer

        if many:
            if self.full or self.extended:
                if ns:
                    # noinspection PyUnresolvedReferences
                    res = ser_class(self.request, ns, many=True).data
                else:
                    res = []
            else:
                res = list(ns.values_list('zpool', flat=True))
        else:
            # noinspection PyUnresolvedReferences
            res = ser_class(self.request, ns).data

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    def post(self, ns):
        """Create node-storage"""
        ns.storage = Storage(name='%s@%s' % (ns.zpool, ns.node.hostname), alias=ns.zpool, owner=self.request.user)

        try:
            ns.storage.size = ns.node.zpools[ns.zpool]['size']
        except KeyError:
            pass

        ser = NodeStorageSerializer(self.request, ns, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=ns, dc_bound=False)

        with transaction.atomic():
            storage = ser.object.storage
            storage.save()
            ser.object.storage = storage
            ser.object.save(update_dcnode_resources=(ser.object.zpool == ser.object.node.zpool))

        return SuccessTaskResponse(self.request, ser.data, status=HTTP_201_CREATED, obj=ns, dc_bound=False,
                                   detail_dict=ser.detail_dict(), msg=LOG_NS_CREATE)

    def put(self, ns):
        """Update node-storage"""
        ser = NodeStorageSerializer(self.request, ns, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=ns, dc_bound=False)

        update_storage_resources = ser.update_storage_resources
        is_zones_pool = ser.object.zpool == ser.object.node.zpool

        try:
            with transaction.atomic():
                ser.object.storage.save()
                ser.object.save(update_resources=update_storage_resources, update_dcnode_resources=is_zones_pool)

                if update_storage_resources:
                    if ns.storage.size_free < 0:
                        raise IntegrityError('disk_check')
                    elif is_zones_pool and ns.node.dcnode_set.filter(dc__in=ns.dc.all(), ram_free__lt=0).exists():
                        raise IntegrityError('disk_check')

        except IntegrityError as exc:
            # size constraint was violated on vms_dcnode (can happen when DcNode strategy is set to RESERVED)
            # OR a an exception was raised above
            if 'disk_check' in str(exc):
                errors = {'size_coef': ser.error_negative_resources}
                return FailureTaskResponse(self.request, errors, obj=ns, dc_bound=False)
            else:
                raise exc

        if ser.update_storage_resources:  # size_free changed
            ser.reload()

        return SuccessTaskResponse(self.request, ser.data, obj=ns, detail_dict=ser.detail_dict(), msg=LOG_NS_UPDATE,
                                   dc_bound=False)

    def delete(self, ns):
        """Update node-storage"""
        ser = NodeStorageSerializer(self.request, ns)
        node = ns.node

        for vm in node.vm_set.all():
            if ns.zpool in vm.get_used_disk_pools():  # active + current
                raise PreconditionRequired(_('Storage is used by some VMs'))

        if node.is_backup:
            if ns.backup_set.exists():
                raise PreconditionRequired(_('Storage is used by some VM backups'))

        obj = ns.log_list
        owner = ns.storage.owner
        ser.object.delete()  # Will delete Storage in post_delete

        return SuccessTaskResponse(self.request, None, obj=obj, owner=owner, msg=LOG_NS_DELETE, dc_bound=False)
