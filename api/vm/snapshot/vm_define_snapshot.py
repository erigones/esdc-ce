from logging import getLogger

from api import status as scode
from api.api_views import APIView
from api.exceptions import APIError
from api.utils.request import set_request_method
from api.utils.db import get_object
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.vm.messages import LOG_SNAPDEF_CREATE, LOG_SNAPDEF_UPDATE, LOG_SNAPDEF_DELETE
from api.vm.snapshot.utils import is_vm_operational, detail_dict, get_disk_id
from api.vm.snapshot.serializers import (SnapshotDefineSerializer, ExtendedSnapshotDefineSerializer,
                                         define_schedule_defaults)
from vms.models import SnapshotDefine

logger = getLogger(__name__)


class SnapshotDefineView(APIView):
    order_by_default = ('vm__hostname', '-id')
    order_by_fields = ('name', 'disk_id')
    order_by_field_map = {'hostname': 'vm__hostname', 'created': 'id'}

    def get(self, vm, define, many=False, extended=False):
        """Get snapshot definition(s)"""
        if extended:
            ser_class = ExtendedSnapshotDefineSerializer
        else:
            ser_class = SnapshotDefineSerializer

        if many:
            if self.full or self.extended:
                if define:
                    # noinspection PyUnresolvedReferences
                    res = ser_class(self.request, define, many=True).data
                else:
                    res = []
            else:
                res = list(define.values_list('name', flat=True))
        else:
            # noinspection PyUnresolvedReferences
            res = ser_class(self.request, define).data

        return SuccessTaskResponse(self.request, res, vm=vm)

    # noinspection PyUnusedLocal
    @is_vm_operational
    def post(self, vm, define, **kwargs):
        """Create snapshot definition"""
        data2 = define_schedule_defaults(define.name)
        data2.update(self.data)
        ser = SnapshotDefineSerializer(self.request, define, data=data2)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, vm=vm)

        ser.object.save()
        return SuccessTaskResponse(self.request, ser.data, status=scode.HTTP_201_CREATED, vm=vm,
                                   detail_dict=detail_dict('snapdef', ser),
                                   msg=LOG_SNAPDEF_CREATE)

    # noinspection PyUnusedLocal
    @is_vm_operational
    def put(self, vm, define, **kwargs):
        """Update snapshot definition"""
        ser = SnapshotDefineSerializer(self.request, define, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, vm=vm)

        ser.object.save()
        return SuccessTaskResponse(self.request, ser.data, vm=vm, detail_dict=detail_dict('snapdef', ser),
                                   msg=LOG_SNAPDEF_UPDATE)

    # noinspection PyUnusedLocal
    @is_vm_operational
    def delete(self, vm, define, **kwargs):
        """Delete snapshot definition"""
        ser = SnapshotDefineSerializer(self.request, define)

        ser.object.delete()

        return SuccessTaskResponse(self.request, None, vm=vm, detail_dict=detail_dict('snapdef', ser, data={}),
                                   msg=LOG_SNAPDEF_DELETE)

    @classmethod
    def create_from_template(cls, request, vm, vm_define_snapshot, log=logger):
        """Create snapshot definitions from vm.template.vm_define_snapshot list"""
        if vm_define_snapshot and isinstance(vm_define_snapshot, list):
            request = set_request_method(request, 'POST')

            for i, data in enumerate(vm_define_snapshot):
                try:
                    try:
                        snapdef = data['snapdef']
                    except KeyError:
                        snapdef = data['name']

                    disk_id, real_disk_id, zfs_filesystem = get_disk_id(request, vm, data)
                    log.info('Creating snapshot definition [%d] "%s" for vm=%s, disk_id=%d defined by template %s',
                             i, snapdef, vm, disk_id, vm.template)
                    define = get_object(request, SnapshotDefine, {'name': snapdef, 'vm': vm, 'disk_id': real_disk_id},
                                        sr=('vm', 'periodic_task', 'periodic_task__crontab'))
                    res = cls(request, data=data).post(vm, define)

                    if res.status_code != scode.HTTP_201_CREATED:
                        raise APIError('vm_define_snapshot error [%s]: %s' % (res.status_code, res.data))
                except Exception as ex:
                    log.warn('Failed to create snapshot definition [%d] for vm=%s defined by template %s with '
                             'data="%s". Error: %s', i, vm, vm.template, data, ex)
