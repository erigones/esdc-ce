from django.conf import settings

from que.tasks import execute
from api.api_views import APIView
from api.exceptions import VmIsNotOperational, VmHasPendingTasks, VmIsLocked, PreconditionRequired
from api.task.response import FailureTaskResponse, TaskResponse
from api.vm.utils import get_vm
from api.vm.messages import LOG_MIGRATE
from api.vm.migrate.serializers import VmMigrateSerializer


class VmMigrate(APIView):
    """
    api.vm.migrate.views.vm_migrate
    """
    def __init__(self, request, hostname, data):
        super(VmMigrate, self).__init__(request)
        self.hostname = hostname
        self.data = data
        self.vm = get_vm(request, hostname, exists_ok=True, noexists_fail=True)

    def put(self):
        request, vm = self.request, self.vm

        if vm.uuid in settings.VMS_INTERNAL:
            raise PreconditionRequired('Internal VM can\'t be migrated')

        if vm.locked:
            raise VmIsLocked

        if vm.status not in (vm.STOPPED, vm.RUNNING):
            raise VmIsNotOperational('VM is not stopped or running')

        if vm.json_changed():
            raise PreconditionRequired('VM definition has changed; Update first')

        ser = VmMigrateSerializer(request, vm, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, vm=vm)

        if vm.tasks:
            raise VmHasPendingTasks

        err = True
        ghost_vm = None
        # Set VM to nonready (+"api lock")
        vm.set_notready()

        try:
            # Create a dummy/placeholder VM
            ghost_vm = ser.save_ghost_vm()

            # Possible node_image import task which will block this task on node worker
            block_key = ser.node_image_import()

            # Prepare task data
            apiview = {'view': 'vm_migrate', 'method': request.method, 'hostname': vm.hostname}
            lock = 'vm_migrate vm:%s' % vm.uuid
            meta = {
                'output': {'returncode': 'returncode', 'stderr': 'message', 'stdout': 'json'},
                'replace_stderr': ((vm.uuid, vm.hostname),),
                'msg': LOG_MIGRATE,
                'vm_uuid': vm.uuid,
                'slave_vm_uuid': ghost_vm.uuid,
                'apiview': apiview,
            }
            callback = ('api.vm.migrate.tasks.vm_migrate_cb', {'vm_uuid': vm.uuid, 'slave_vm_uuid': ghost_vm.uuid})

            # Execute task
            tid, err = execute(request, vm.owner.id, ser.esmigrate_cmd, meta=meta, lock=lock,
                               callback=callback, queue=vm.node.fast_queue, block_key=block_key)

            if err:  # Error, revert VM status, delete placeholder VM
                return FailureTaskResponse(request, err, vm=vm)
            else:  # Success, task is running
                return TaskResponse(request, tid, msg=LOG_MIGRATE, vm=vm, api_view=apiview,
                                    detail_dict=ser.detail_dict(), data=self.data)
        finally:
            if err:
                vm.revert_notready()
                if ghost_vm:
                    ghost_vm.delete()
