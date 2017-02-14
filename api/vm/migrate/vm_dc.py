from django.db.transaction import atomic

from api.api_views import APIView
from api.exceptions import VmIsNotOperational, VmHasPendingTasks, VmIsLocked, PreconditionRequired
from api.task.response import FailureTaskResponse, SuccessTaskResponse
from api.task.utils import task_log_success
from api.vm.utils import get_vm
from api.vm.messages import LOG_MIGRATE_DC
from api.vm.migrate.serializers import VmDcSerializer
from que.utils import task_id_from_task_id
from vms.models import TaskLogEntry, Backup, Snapshot


class VmDc(APIView):
    """
    api.vm.migrate.views.vm_dc
    """
    def __init__(self, request, hostname_or_uuid, data):
        super(VmDc, self).__init__(request)
        self.hostname_or_uuid = hostname_or_uuid
        self.data = data
        self.vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True)

    @atomic
    def put(self):
        request, vm = self.request, self.vm

        if vm.locked:
            raise VmIsLocked

        if vm.status not in (vm.STOPPED, vm.RUNNING, vm.NOTCREATED):
            raise VmIsNotOperational('VM is not stopped, running or notcreated')

        if vm.json_changed():
            raise PreconditionRequired('VM definition has changed; Update first')

        ser = VmDcSerializer(request, vm, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, vm=vm)

        if vm.tasks:
            raise VmHasPendingTasks

        old_dc = vm.dc
        dc = ser.dc
        # Change DC for one VM, repeat this for other VM + Recalculate node & storage resources in target and source
        vm.dc = dc
        vm.save(update_node_resources=True, update_storage_resources=True)
        # Change task log entries DC for target VM
        TaskLogEntry.objects.filter(object_pk=vm.uuid).update(dc=dc)
        # Change related VM backup's DC
        Backup.objects.filter(vm=vm).update(dc=dc)

        for ns in ser.nss:  # Issue #chili-885
            for i in (dc, old_dc):
                Backup.update_resources(ns, vm, i)
                Snapshot.update_resources(ns, vm, i)

        detail = 'Successfully migrated VM %s from datacenter %s to datacenter %s' % (vm.hostname, old_dc.name, dc.name)
        # Will create task log entry in old DC
        res = SuccessTaskResponse(request, detail, vm=vm, msg=LOG_MIGRATE_DC, detail=detail)
        # Create task log entry in new DC too
        task_log_success(task_id_from_task_id(res.data.get('task_id'), dc_id=dc.id), LOG_MIGRATE_DC, obj=vm,
                         detail=detail, update_user_tasks=False)

        return res
