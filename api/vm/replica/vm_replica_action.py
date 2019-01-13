from api.exceptions import PreconditionRequired, VmHasPendingTasks
from api.serializers import ForceSerializer, APIValidationError
from api.vm.define.slave_vm_define import SlaveVmDefine
from api.vm.replica.messages import LOG_REPLICA_FAILOVER, LOG_REPLICA_REINIT
from api.vm.replica.vm_replica import VmReplicaBaseView


class VmReplicaFailover(VmReplicaBaseView):
    """
    api.vm.replica.views.vm_replica_failover
    """
    _api_view_ = 'vm_replica_failover'
    _check_node_status = None

    def put(self):
        """Failover to slave VM"""
        vm, slave_vm = self.vm, self.slave_vm

        if slave_vm.rep_reinit_required:
            raise PreconditionRequired('Reinitialization is required')

        if not slave_vm.reserve_resources:  # We need to check whether there is free CPU and RAM on slave VM's node
            slave_vm_define = SlaveVmDefine(slave_vm)

            try:
                slave_vm_define.validate_node_resources(ignore_cpu_ram=False, ignore_disk=True)
            except APIValidationError:
                raise PreconditionRequired('Not enough free resources on target node')

        if slave_vm.sync_status == slave_vm.DIS:  # service does not exist
            cmd = self.CMD['failover']
        else:
            cmd = self.CMD['svc-remove'] + ' && ' + self.CMD['failover']

        if vm.tasks:
            force = ForceSerializer(data=self.data, default=False).is_true()
            if not force:
                raise VmHasPendingTasks
        else:
            force = False

        orig_status = vm.status
        # Set VM to nonready
        vm.set_notready()

        try:
            return self._run_execute(LOG_REPLICA_FAILOVER, cmd, force=force, orig_status=orig_status)
        finally:
            if not self._success:
                vm.revert_notready()


class VmReplicaReinit(VmReplicaBaseView):
    """
    api.vm.replica.views.vm_replica_reinit
    """
    _api_view_ = 'vm_replica_reinit'

    def put(self):
        """Reinitialize old master VM -> reverse replication"""
        self._check_master_vm()
        slave_vm = self.slave_vm

        if not slave_vm.rep_reinit_required:
            raise PreconditionRequired('Reinitialization is not required')

        slave_vm.rep_enabled = True  # Enable replication service
        cmd = self.CMD['reinit'] + ' && ' + self.CMD['svc-create'] % self._esrep_svc_opts

        return self._run_execute(LOG_REPLICA_REINIT, cmd)
