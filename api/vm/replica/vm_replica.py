from logging import getLogger

from django.conf import settings
from frozendict import frozendict

from que.tasks import execute
from que.utils import task_id_from_string, task_prefix_from_task_id
from vms.models import SlaveVm
from api import status as scode
from api.api_views import APIView
from api.exceptions import NodeIsNotOperational, VmIsNotOperational, VmHasPendingTasks, PreconditionRequired
from api.task.response import SuccessTaskResponse, FailureTaskResponse, TaskResponse
from api.utils.db import get_object
from api.vm.utils import get_vm
from api.vm.replica.messages import LOG_REPLICA_CREATE, LOG_REPLICA_UPDATE, LOG_REPLICA_DELETE
from api.vm.replica.serializers import VmReplicaSerializer

logger = getLogger(__name__)


class VmReplicaBaseView(APIView):
    """
    Base API view helper for vm_replica, vm_replica_failover and vm_replica_reinit views.
    """
    CMD = frozendict({
        'init': 'esrep init -m {master_uuid} -s {slave_uuid} -H {master_node} -i {id} -p -j - %s',
        'destroy': 'esrep destroy -m {master_uuid} -s {slave_uuid} -H {master_node} -i {id}',
        'failover': 'esrep failover -m {master_uuid} -s {slave_uuid} -H {master_node} -i {id} -f',
        'reinit': 'esrep reinit -m {master_uuid} -s {slave_uuid} -H {master_node} -i {id}',
        'destroy-clear': 'esrep destroy-clear -m {master_uuid} -s {slave_uuid} -H {master_node} -i {id}',
        'svc-create': 'esrep svc-create -m {master_uuid} -s {slave_uuid} -H {master_node} -i {id} %s',
        'svc-remove': 'esrep svc-remove -m {master_uuid} -s {slave_uuid} -i {id}',
        'svc-enable': 'esrep svc-enable -m {master_uuid} -s {slave_uuid} -i {id}',
        'svc-disable': 'esrep svc-disable -m {master_uuid} -s {slave_uuid} -i {id}',
    })
    _api_view_ = NotImplemented
    # Master node must be online even during delete (vm_replica), because disk zfs properties must be removed
    _check_node_status = ('POST', 'PUT', 'DELETE')

    def __init__(self, request, hostname_or_uuid, repname, data):
        super(VmReplicaBaseView, self).__init__(request)
        self.repname = repname
        self.data = data
        self._success = False
        self.vm = vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True,
                              check_node_status=self._check_node_status)

        if repname is None:  # Exclude migration ghost VMs
            self.slave_vm = SlaveVm.objects.select_related('vm', 'master_vm', 'vm__node')\
                                           .filter(master_vm=vm).exclude(name=u'').order_by('name')
        else:
            self.slave_vm = get_object(request, SlaveVm, {'master_vm': vm, 'name': repname},
                                       sr=('vm', 'master_vm', 'vm__node'),
                                       create_attrs={'_master_vm': vm, 'name': repname})

    @property
    def _esrep_callback(self):
        vm = self.vm
        task_id = task_id_from_string(settings.SYSTEM_USER, owner_id=vm.owner.id, dc_id=vm.dc.id)
        task_prefix = ''.join(task_prefix_from_task_id(task_id))
        return 'que.replication:esrep_sync_cb:%s' % task_prefix

    @property
    def _esrep_svc_opts(self):
        slave_vm = self.slave_vm
        opts = ['-t %d' % slave_vm.rep_sleep_time, '-c %s' % self._esrep_callback]

        if slave_vm.rep_enabled:
            opts.append('-e')

        bwlimit = slave_vm.rep_bwlimit
        if bwlimit:
            opts.append('-l %d' % bwlimit)

        return ' '.join(opts)

    def _check_master_vm(self):
        vm = self.vm

        if vm.status not in (vm.RUNNING, vm.STOPPED, vm.STOPPING):
            raise VmIsNotOperational

    def _check_slave_vm_node(self):
        node = self.slave_vm.vm.node

        if node.status != node.ONLINE:
            raise NodeIsNotOperational

    def _run_execute(self, msg, cmd, stdin=None, detail_dict=None, block_key=None, **apiview_kwargs):
        request, master_vm, slave_vm, repname = self.request, self.vm, self.slave_vm, self.slave_vm.name

        if detail_dict is None:
            detail_dict = {'repname': repname}

        # Prepare task data
        apiview = {
            'view': self._api_view_,
            'method': request.method,
            'hostname': master_vm.hostname,
            'repname': repname
        }
        apiview.update(apiview_kwargs)
        meta = {
            'output': {'returncode': 'returncode', 'stdout': 'jsons', 'stderr': 'message'},
            'replace_stdout': ((master_vm.uuid, master_vm.hostname), (slave_vm.uuid, repname)),
            'msg': msg,
            'vm_uuid': master_vm.uuid,
            'slave_vm_uuid': slave_vm.uuid,
            'apiview': apiview,
        }

        lock = 'vm_replica vm:%s' % master_vm.uuid
        callback = (
            'api.vm.replica.tasks.%s_cb' % self._api_view_,
            {'vm_uuid': master_vm.uuid, 'slave_vm_uuid': slave_vm.uuid}
        )
        cmd = cmd.format(
            master_uuid=master_vm.uuid,
            slave_uuid=slave_vm.uuid,
            master_node=master_vm.node.address,
            id=slave_vm.rep_id,
        )

        self._check_slave_vm_node()
        # Execute task
        tid, err = execute(request, master_vm.owner.id, cmd, meta=meta, lock=lock, callback=callback, stdin=stdin,
                           queue=slave_vm.node.fast_queue, block_key=block_key)

        if err:
            return FailureTaskResponse(request, err, vm=master_vm)
        else:
            self._success = True
            return TaskResponse(request, tid, msg=msg, vm=master_vm, api_view=apiview,
                                detail_dict=detail_dict, data=self.data)


class VmReplica(VmReplicaBaseView):
    """
    api.vm.replica.views.vm_replica
    """
    _api_view_ = 'vm_replica'

    @property
    def _esrep_init_opts(self):
        slave_vm = self.slave_vm
        bwlimit = slave_vm.rep_bwlimit

        if bwlimit:
            return '-l %d' % bwlimit
        else:
            return ''

    def get(self, many=False):
        """Return slave server status and details"""
        slave_vm = self.slave_vm

        if many:
            if self.full:
                if slave_vm:
                    res = VmReplicaSerializer(self.request, slave_vm, many=True).data
                else:
                    res = []
            else:
                res = list(slave_vm.values_list('name', flat=True))
        else:
            res = VmReplicaSerializer(self.request, slave_vm).data

        return SuccessTaskResponse(self.request, res)

    def post(self):
        """Create and initialize slave VM and create replication service"""
        request, vm = self.request, self.vm

        if vm.status not in (vm.STOPPED, vm.RUNNING):
            raise VmIsNotOperational('VM is not stopped or running')

        if vm.json_changed():
            raise PreconditionRequired('VM definition has changed; Update first')

        ser = VmReplicaSerializer(request, self.slave_vm, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, vm=vm)

        if vm.tasks:
            raise VmHasPendingTasks

        cmd = self.CMD['init'] % self._esrep_init_opts + ' && ' + self.CMD['svc-create'] % self._esrep_svc_opts
        slave_vm = None
        # Set VM to nonready (+"api lock")
        vm.set_notready()

        try:
            # Create slave VM
            slave_vm = ser.save_slave_vm()
            stdin = slave_vm.vm.fix_json(resize=True).dump()
            logger.debug('Creating new slave VM %s on node %s with json: """%s"""', slave_vm, slave_vm.node, stdin)

            return self._run_execute(LOG_REPLICA_CREATE, cmd, stdin=stdin, detail_dict=ser.detail_dict(),
                                     block_key=ser.node_image_import())
        finally:
            if not self._success:
                vm.revert_notready()
                if slave_vm:
                    slave_vm.delete()

    def put(self):
        """Re-create replication service with new settings"""
        slave_vm = self.slave_vm
        self._check_master_vm()

        if slave_vm.rep_reinit_required:
            raise PreconditionRequired('Reinitialization is required')

        # Check this before validating the serializer, because it updates the slave_vm.sync_status
        if slave_vm.sync_status == SlaveVm.DIS:  # service does not exist
            cmd = ''
        else:
            cmd = self.CMD['svc-remove'] + ' && '

        ser = VmReplicaSerializer(self.request, slave_vm, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, vm=self.vm)

        dd = ser.detail_dict()
        only_one_attr_changed = len(dd) == 2

        if ser.reserve_resources_changed:
            # We need to save the reserve_resources attribute into SlaveVm;
            # However, the current slave_vm object may have other attributes modified by the serializer
            slave_vm_copy = SlaveVm.objects.get(pk=slave_vm.pk)
            slave_vm_copy.reserve_resources = slave_vm.reserve_resources
            slave_vm_copy.save(update_fields=('enc_json',))
            slave_vm_copy.vm.save(update_node_resources=True)

            if only_one_attr_changed:
                return SuccessTaskResponse(self.request, ser.data, vm=self.vm, msg=LOG_REPLICA_UPDATE, detail_dict=dd,
                                           status=scode.HTTP_205_RESET_CONTENT)

        if cmd and only_one_attr_changed and 'enabled' in dd:
            # Service exists on node and only status change is requested
            if slave_vm.rep_enabled:
                cmd = self.CMD['svc-enable']
            else:
                cmd = self.CMD['svc-disable']
        else:
            cmd += self.CMD['svc-create'] % self._esrep_svc_opts

        return self._run_execute(LOG_REPLICA_UPDATE, cmd, detail_dict=dd)

    def delete(self):
        """Stop replication service and delete slave VM"""
        slave_vm = self.slave_vm
        self._check_master_vm()

        if slave_vm.rep_reinit_required:  # The replica is an old master VM
            assert slave_vm.sync_status == SlaveVm.DIS
            cmd = self.CMD['destroy-clear']  # TODO: stop required?
            force = True
        else:
            if slave_vm.sync_status == SlaveVm.DIS:  # service does not exist
                cmd = self.CMD['destroy']
            else:
                cmd = self.CMD['svc-remove'] + ' && ' + self.CMD['destroy']
            force = False

        return self._run_execute(LOG_REPLICA_DELETE, cmd, force=force)
