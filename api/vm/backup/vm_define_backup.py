from logging import getLogger

from api import status as scode
from api.api_views import APIView
from api.exceptions import APIError
from api.utils.request import set_request_method
from api.utils.db import get_object
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.vm.messages import LOG_BKPDEF_CREATE, LOG_BKPDEF_UPDATE, LOG_BKPDEF_DELETE
from api.vm.backup.serializers import BackupDefineSerializer, ExtendedBackupDefineSerializer
from api.vm.snapshot.utils import is_vm_operational, detail_dict, get_disk_id
from api.vm.snapshot.serializers import define_schedule_defaults
from vms.models import BackupDefine

logger = getLogger(__name__)


class BackupDefineView(APIView):
    order_by_default = ('vm__hostname', '-id')
    order_by_fields = ('name', 'disk_id')
    order_by_field_map = {'hostname': 'vm__hostname', 'created': 'id'}

    def get(self, vm, define, many=False, extended=False):
        """Get backup definition(s)"""
        if extended:
            ser_class = ExtendedBackupDefineSerializer
        else:
            ser_class = BackupDefineSerializer

        if many:
            if self.full or self.extended:
                if define:
                    res = ser_class(self.request, define, many=True).data
                else:
                    res = []
            else:
                res = list(define.values_list('name', flat=True))
        else:
            res = ser_class(self.request, define).data

        return SuccessTaskResponse(self.request, res, vm=vm)

    # noinspection PyUnusedLocal
    @is_vm_operational
    def post(self, vm, define, vm_template=False, **kwargs):
        """Create backup definition"""
        data2 = define_schedule_defaults(define.name)
        data2.update(self.data)
        ser = BackupDefineSerializer(self.request, define, data=data2, vm_template=vm_template)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, vm=vm)

        ser.object.save()
        return SuccessTaskResponse(self.request, ser.data, status=scode.HTTP_201_CREATED, vm=vm,
                                   detail_dict=detail_dict('bkpdef', ser),
                                   msg=LOG_BKPDEF_CREATE)

    # noinspection PyUnusedLocal
    @is_vm_operational
    def put(self, vm, define, **kwargs):
        """Update backup definition"""
        ser = BackupDefineSerializer(self.request, define, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, vm=vm)

        ser.object.save()
        return SuccessTaskResponse(self.request, ser.data, vm=vm, detail_dict=detail_dict('bkpdef', ser),
                                   msg=LOG_BKPDEF_UPDATE)

    # noinspection PyUnusedLocal
    @is_vm_operational
    def delete(self, vm, define, **kwargs):
        """Delete backup definition"""
        ser = BackupDefineSerializer(self.request, define)

        ser.object.delete()

        return SuccessTaskResponse(self.request, None, vm=vm, detail_dict=detail_dict('bkpdef', ser, data={}),
                                   msg=LOG_BKPDEF_DELETE)

    @classmethod
    def create_from_template(cls, request, vm, vm_define_backup, log=logger):
        """Create backup definitions from vm.template.vm_define_backup list"""
        if vm_define_backup and isinstance(vm_define_backup, list):
            old_method = request.method
            request = set_request_method(request, 'POST')

            for i, data in enumerate(vm_define_backup):
                try:
                    try:
                        bkpdef = data['bkpdef']
                    except KeyError:
                        bkpdef = data['name']

                    disk_id, real_disk_id, zfs_filesystem = get_disk_id(request, vm, data)
                    log.info('Creating backup definition [%d] "%s" for vm=%s, disk_id=%d defined by template %s',
                             i, bkpdef, vm, disk_id, vm.template)
                    define = get_object(request, BackupDefine, {'name': bkpdef, 'vm': vm, 'disk_id': real_disk_id})
                    res = cls(request, data=data).post(vm, define, vm_template=True)

                    if res.status_code != scode.HTTP_201_CREATED:
                        raise APIError('vm_define_backup error [%s]: %s' % (res.status_code, res.data))
                except Exception as ex:
                    log.warn('Failed to create backup definition [%d] for vm=%s defined by template %s with '
                             'data="%s". Error: %s', i, vm, vm.template, data, ex)

            set_request_method(request, old_method)
