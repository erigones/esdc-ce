from vms.models import Backup
from que import TT_EXEC, TT_AUTO
from api.api_views import TaskAPIView
from api.task.response import SuccessTaskResponse
from api.exceptions import VmIsNotOperational, NodeIsNotOperational, ExpectationFailed, ObjectNotFound
from api.vm.utils import get_vm
from api.vm.messages import LOG_BKPS_DELETE
from api.vm.backup.serializers import BackupSerializer
from api.vm.backup.utils import BACKUP_TASK_EXPIRES, get_backups, filter_backup_define, get_backup_cmd
from api.vm.snapshot.utils import filter_disk_id


class VmBackupList(TaskAPIView):
    """
    api.vm.backup.views.vm_backup_list
    """
    order_by_default = ('-id',)
    order_by_fields = ('name', 'size', 'time')
    order_by_field_map = {'created': 'id', 'hostname': 'vm_hostname', 'disk_id': 'vm_disk_id'}
    LOCK = 'vm_backup vm:%s disk:%s'

    def __init__(self, request, hostname_or_uuid, data, node=None):
        super(VmBackupList, self).__init__(request)
        self.hostname_or_uuid = hostname_or_uuid
        self.data = data
        self.node = node

        if node:
            self._init_node(node)
        else:
            self._init_vm()

        # Task type (a = automatic, e = manual)
        if getattr(request, 'define_id', None):
            self.tt = TT_AUTO
        else:
            self.tt = TT_EXEC

    def _init_node(self, node):
        request, data = self.request, self.data
        bkp_filter = {'node': node}

        if not request.user.is_staff:  # DC admin:
            bkp_filter['dc'] = request.dc

        self.bkp_filter = self.filter_backup_vm(bkp_filter, data)

    def _init_vm(self):
        request, data, hostname_or_uuid = self.request, self.data, self.hostname_or_uuid
        bkp_filter = {'dc': request.dc}

        try:
            if 'hostname' in data:  # Force original hostname
                raise ObjectNotFound
            # No need to check vm.node.status; only backup node status is important
            vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True, check_node_status=None)
        except ObjectNotFound:
            vm = None
            bkp_filter['vm_hostname'] = hostname_or_uuid
        else:
            bkp_filter['vm'] = vm

        self.vm = vm
        self.bkp_filter = bkp_filter

    @staticmethod
    def filter_backup_vm(query_filter, data):
        """Validate server hostname and update dictionary used for queryset filtering"""
        if 'vm' in data:
            if data['vm']:
                query_filter['vm_hostname'] = data['vm']
            else:
                query_filter['vm__isnull'] = True

        return query_filter

    def get(self):
        request, data = self.request, self.data
        bkp_filter = filter_disk_id(None, self.bkp_filter, data)  # vm_disk_id instead of disk_id
        bkp_filter = filter_backup_define(bkp_filter, data)

        # TODO: check indexes
        bkps = Backup.objects.select_related('node', 'define', 'vm').filter(**bkp_filter).order_by(*self.order_by)

        if self.full or self.extended:
            if bkps:
                res = BackupSerializer(request, bkps, node_view=self.node, many=True).data
            else:
                res = []
        else:
            res = list(bkps.values_list('name', flat=True))

        return SuccessTaskResponse(request, res)

    # noinspection PyMethodMayBeStatic
    def _check_vm(self, vm):
        if vm.status not in (vm.RUNNING, vm.STOPPED, vm.STOPPING):
            raise VmIsNotOperational

    # noinspection PyMethodMayBeStatic
    def _check_bkp_node(self, node):
        if node.status != node.ONLINE:
            raise NodeIsNotOperational

    def _check_bkp(self):
        if any(bkp.status != Backup.OK for bkp in self.bkps):
            raise ExpectationFailed('VM backup status is not OK')

    def _meta(self):
        bkp = self.bkp
        # noinspection PyProtectedMember
        return {
            'output': {'returncode': 'returncode', 'stdout': 'json', 'stderr': 'message', 'detail': self.detail},
            'replace_stderr': ((bkp.vm_uuid, bkp.vm_hostname),),
            'msg': self.msg,
            'apiview': self.apiview,
            self.obj._pk_key: self.obj.pk,
        }

    def _callback(self):
        bkp_ids = [b.id for b in self.bkps]
        # noinspection PyProtectedMember
        return 'api.vm.backup.tasks.vm_backup_list_cb', {self.obj._pk_key: self.obj.pk, 'bkp_ids': bkp_ids}

    def _apiview(self):
        return {'view': 'vm_backup_list', 'method': self.request.method, 'hostname': self.bkp.vm_hostname_real,
                'disk_id': self.disk_id, 'bkpnames': self.bkpnames, 'vm': bool(self.bkp.vm)}

    def _detail(self, bkpnames=None):
        bkpnames = bkpnames or self.bkpnames
        return "hostname='%s', bkpnames='%s', disk_id=%s" % (self.bkp.vm_hostname, ','.join(bkpnames), self.disk_id)

    def execute(self, cmd, **kwargs):
        super(VmBackupList, self).execute(cmd, meta=self._meta(), callback=self._callback(), tt=self.tt,
                                          queue=self.bkp.node.backup_queue, expires=BACKUP_TASK_EXPIRES, **kwargs)
        return not bool(self.error)

    # noinspection PyAttributeOutsideInit
    def delete(self):
        """Delete multiple backups"""
        # TODO: not documented :(
        bkp_filter = filter_disk_id(None, self.bkp_filter, self.data, default=1)  # vm_disk_id instead of disk_id
        bkps, __ = get_backups(self.request, bkp_filter, self.data)   # Parse data['bkpnames']
        bkps_lost = bkps.filter(status=Backup.LOST)
        bkp = bkps[0]
        vm = bkp.vm
        self.bkp = bkp
        self.disk_id = bkp.array_disk_id

        if vm:
            self._check_vm(vm)
            obj = vm
        else:
            obj = bkp.node

        if bkps_lost:
            self._check_bkp_node(bkp.node)
            _result = {'message': 'Backups successfully deleted from DB'}
            _detail = self._detail(bkpnames=[i.name for i in bkps_lost])
            bkps_lost.delete()
            res = SuccessTaskResponse(self.request, _result, msg=LOG_BKPS_DELETE, obj=obj, detail=_detail)
            bkps = bkps.filter(status=Backup.OK)  # Work with OK backups from now on

            if not bkps:
                return res

        bkpnames = [i.name for i in bkps]
        self.bkps = bkps
        self.bkpnames = bkpnames
        self._check_bkp()
        self._check_bkp_node(bkp.node)
        self.msg = LOG_BKPS_DELETE
        self.obj = obj

        if self.execute(get_backup_cmd('delete', bkp, bkps=bkps), lock=self.LOCK % (bkp.vm_uuid, bkp.disk_id)):
            bkps.update(status=Backup.PENDING)
            return self.task_response

        return self.error_response
