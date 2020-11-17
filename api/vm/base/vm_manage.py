from logging import getLogger

from django.utils.six import iteritems

from que.tasks import execute
from vms.models import Image, ImageVm
from api.api_views import APIView
from api.exceptions import (PermissionDenied, VmIsNotOperational, VmIsLocked, VmHasPendingTasks, PreconditionRequired,
                            ExpectationFailed, NodeIsNotOperational, InvalidInput)
from api.serializers import ForceSerializer
from api.task.utils import TaskID
from api.task.response import SuccessTaskResponse, FailureTaskResponse, TaskResponse
from api.signals import vm_updated
from api.vm.utils import get_vms, get_vm
from api.node.utils import get_node
from api.vm.messages import LOG_VM_CREATE, LOG_VM_RECREATE, LOG_VM_UPDATE, LOG_VM_DELETE
from api.vm.base.serializers import VmCreateSerializer, VmSerializer, ExtendedVmSerializer
from api.vm.define.vm_define import VmDefineView
from api.vm.status.tasks import vm_status_changed
from api.node.image.api_views import NodeImageView

logger = getLogger(__name__)

VM_VM_EXPIRES = 1200  # Higher expire timeout for VM delete and create tasks


class VmManage(APIView):
    """
    api.vm.base.views.vm_manage
    """
    order_by_default = order_by_fields = ('hostname',)

    def __init__(self, request, hostname_or_uuid, data):
        super(VmManage, self).__init__(request)
        self.hostname_or_uuid = hostname_or_uuid
        self.data = data

        if request.method == 'GET':  # get() uses different methods for getting vm(s) object(s)
            self.vm = None
        else:
            self.vm = get_vm(request, hostname_or_uuid, exists_ok=True, noexists_fail=True,
                             check_node_status=('POST', 'DELETE'))

    @staticmethod
    def compute_bhyve_quota(all_disks_size):
        quota = int(round((2 * (all_disks_size * 1.03)) + (1.5 * all_disks_size)))
        logger.debug('Bhyve VM quota computed to "%s" (from disks size "%")', quota, all_disks_size)
        return quota

    @staticmethod
    def fix_create(vm):
        """SmartOS issue. If a image_uuid is specified then size should be omitted, which is done in vm.fix_json(),
        so run this one before vm.fix_json() to create a command for changing zvol volsize."""
        if not vm.is_hvm():
            return ''

        cmd = ''

        if vm.is_kvm():
            for i, disk in enumerate(vm.json_get_disks()):
                if 'image_uuid' in disk:
                    if disk['size'] != disk['image_size']:
                        _resize = '; zfs set volsize=%sM %s/%s-disk%s >&2; e=$((e+=$?))' % (disk['size'], vm.zpool, vm.uuid, i)
                        cmd += _resize

                        if 'refreservation' in disk:
                            _refres = '; zfs set refreservation=%sM %s/%s-disk%s >&2; e=$((e+=$?))' % (disk['refreservation'],
                                                                                         vm.zpool, vm.uuid, i)
                            cmd += _refres

        elif vm.is_bhyve():
            quota = VmManage.compute_bhyve_quota(vm.get_disk_size())
            _set_quota = '; zfs set quota=%sM %s/%s >&2; e=$((e+=$?))' % (quota, vm.zpool, vm.uuid)
            cmd += _set_quota
            for i, disk in enumerate(vm.json_get_disks()):
                if 'image_uuid' in disk:
                    if disk['size'] != disk['image_size']:
                        _resize = '; zfs set volsize=%sM %s/%s/disk%s >&2; e=$((e+=$?))' % (disk['size'], vm.zpool, vm.uuid, i)
                        cmd += _resize

        return cmd

    @staticmethod
    def fix_update(json_update, vm):
        """SmartOS issue. Modifying json... Creating manual zfs commands if disk.*.size is being changed."""
        cmd = ''
        new_disks_size = 0
        disks = json_update.get('update_disks', [])

        for i, disk in enumerate(disks):
            zfs_filesystem = '/'.join(disk['path'].split('/')[-2:])  # path is the key in update_disks

            if 'size' in disk:
                size = disk.pop('size')
                cmd += '; zfs set volsize=%sM %s >&2; e=$((e+=$?)); ' % (size, zfs_filesystem)

            if 'refreservation' in disk:
                if vm.is_bhyve():
                    del json_update['update_disks'][i]['refreservation']
                else:
                    refr = disk.pop('refreservation')
                    cmd += '; zfs set refreservation=%sM %s >&2; e=$((e+=$?)); ' % (refr, zfs_filesystem)

        if disks and vm.is_bhyve():
            quota = VmManage.compute_bhyve_quota(vm.disk)
            _set_quota = '; zfs set quota=%sM %s/%s >&2; e=$((e+=$?)); ' % (quota, vm.zpool, vm.uuid)
            # if the sum of all disk sizes is growing, we need to update quota first;
            # if we are shrinking, the quota needs to be updated last
            if vm.disk > vm.disk_active:    # grow
                cmd = _set_quota + cmd
            else:
                cmd += _set_quota

        return json_update, cmd

    # noinspection PyUnusedLocal
    @staticmethod
    def validate_update(vm, json_update, os_cmd):
        """Check if (json_update, os_cmd) tuple from fix_update() can be run on a VM"""
        # cmd = zfs set... >&2;
        if os_cmd and vm.snapshot_set.exists():
            raise ExpectationFailed('VM has snapshots')

        return True

    @staticmethod
    def _check_disk_update(disk_update):
        for disk in disk_update:
            if 'model' in disk:
                return True
        return False

    @staticmethod
    def _check_nic_update(nic_update):
        for nic in nic_update:
            if 'model' in nic:
                return True
        return False

    def check_update(self, json_update):
        """Changing most of the VM's parameters does not require a VM to be in stopped state.
         VM has to be stopped when changing some disk/NIC parameters or adding/deleting disks/NICS
         - issue #chili-879."""
        vm = self.vm
        must_be_stopped = False

        for key, val in iteritems(json_update):
            if key in ('add_nics', 'remove_nics', 'add_disks', 'remove_disks'):
                must_be_stopped = True
                break

            if key == 'update_disks':
                if self._check_disk_update(val):
                    must_be_stopped = True
                    break

            if key == 'update_nics':
                if self._check_nic_update(val):
                    must_be_stopped = True
                    break

        if vm.status != vm.STOPPED and must_be_stopped:
            raise PreconditionRequired('VM has to be stopped when updating disks or NICs')

    def node_image_import(self, node, disks):
        for disk in disks:
            if 'image_uuid' in disk:
                ns = node.nodestorage_set.get(zpool=disk['zpool'])

                if not ns.images.filter(uuid=disk['image_uuid']).exists():
                    img = Image.objects.get(uuid=disk['image_uuid'])
                    # Start image import and return block key
                    return NodeImageView.import_for_vm(self.request, ns, img, self.vm)

        return None

    @property
    def apiview(self):
        return {'view': 'vm_manage', 'method': self.request.method, 'hostname': self.vm.hostname}

    @property
    def lock(self):
        return 'vm_manage vm:%s' % self.vm.uuid

    def get(self, many=False):
        request = self.request
        active = self.data.get('active', False)
        sr = ['owner', 'node']

        if self.extended:
            ser_class = ExtendedVmSerializer
            extra = {'select': ExtendedVmSerializer.extra_select}
            sr.append('slavevm')
        else:
            ser_class = VmSerializer
            extra = None

        def set_active(x):
            # Do not revert owner and template, because it could generate lots of queries otherwise
            x.revert_active(revert_owner=False, revert_template=False)
            return x

        if many:
            if self.full or self.extended:
                vms = get_vms(request, sr=sr, order_by=self.order_by)

                if self.extended:
                    # noinspection PyArgumentList
                    vms = vms.extra(**extra).prefetch_related('tags')

                if active:
                    vms = [set_active(vm) for vm in vms]

                if vms:
                    res = ser_class(request, vms, many=True).data
                else:
                    res = []
            else:
                res = list(get_vms(request, order_by=self.order_by).values_list('hostname', flat=True))

        else:
            vm = get_vm(request, self.hostname_or_uuid, exists_ok=True, noexists_fail=True, sr=sr, extra=extra)

            if active:
                set_active(vm)

            res = ser_class(request, vm).data

        return SuccessTaskResponse(self.request, res)

    def post(self):
        request, vm = self.request, self.vm
        ser = VmCreateSerializer(data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, vm=vm)

        if not vm.is_hvm():
            if not (vm.dc.settings.VMS_VM_SSH_KEYS_DEFAULT or vm.owner.usersshkey_set.exists()):
                raise PreconditionRequired('VM owner has no SSH keys available')

        apiview = self.apiview
        # noinspection PyTypeChecker
        cmd = 'vmadm create >&2; e=$? %s; vmadm get %s 2>/dev/null; vmadm start %s >&2; exit $e' % (
            self.fix_create(vm), vm.uuid, vm.uuid)

        recreate = apiview['recreate'] = ser.data['recreate']
        # noinspection PyAugmentAssignment
        if recreate:
            # recreate should be available to every vm owner
            if not (request.user and request.user.is_authenticated()):
                raise PermissionDenied

            if vm.locked:
                raise VmIsLocked

            if vm.status != vm.STOPPED:
                raise VmIsNotOperational('VM is not stopped')

            if not ser.data['force']:
                raise ExpectationFailed('Are you sure?')

            msg = LOG_VM_RECREATE
            # noinspection PyAugmentAssignment
            cmd = 'vmadm delete ' + vm.uuid + ' >&2 && sleep 1; ' + cmd

        elif vm.status == vm.NOTCREATED:
            # only admin
            if not (request.user and request.user.is_admin(request)):
                raise PermissionDenied

            if not vm.node:  # we need to find a node for this vm now
                logger.debug('VM %s has no compute node defined. Choosing node automatically', vm)
                VmDefineView(request).choose_node(vm)
                logger.info('New compute node %s for VM %s was chosen automatically.', vm.node, vm)

            msg = LOG_VM_CREATE

        else:
            raise VmIsNotOperational('VM is already created')

        # Check boot flag (KVM) or disk image (OS) (bug #chili-418)
        if not vm.is_bootable():
            raise PreconditionRequired('VM has no bootable disk')

        if vm.tasks:
            raise VmHasPendingTasks

        old_status = vm.status
        deploy = apiview['deploy'] = vm.is_deploy_needed()
        resize = apiview['resize'] = vm.is_resize_needed()

        if not vm.is_blank():
            vm.set_root_pw()

        # Set new status also for blank VM (where deployment is not needed)
        # This status will be changed in vm_status_event_cb (if everything goes well).
        vm.status = vm.CREATING
        vm.save()  # save status / node / vnc_port / root_pw

        stdin = vm.fix_json(deploy=deploy, resize=resize, recreate=recreate).dump()
        meta = {
            'output': {'returncode': 'returncode', 'stderr': 'message', 'stdout': 'json'},
            'replace_stderr': ((vm.uuid, vm.hostname),),
            'msg': msg,
            'vm_uuid': vm.uuid,
            'apiview': apiview
        }
        callback = ('api.vm.base.tasks.vm_create_cb', {'vm_uuid': vm.uuid})
        err = True

        try:
            # Possible node_image import task which will block this task on node worker
            block_key = self.node_image_import(vm.node, vm.json_get_disks())
            logger.debug('Creating new VM %s on node %s with json: """%s"""', vm, vm.node, stdin)
            logger.debug('Create command: """%s"""', cmd)
            tid, err = execute(request, vm.owner.id, cmd, stdin=stdin, meta=meta, expires=VM_VM_EXPIRES, lock=self.lock,
                               callback=callback, queue=vm.node.slow_queue, block_key=block_key)

            if err:
                return FailureTaskResponse(request, err, vm=vm)
            else:
                # Inform user about creating
                vm_status_changed(tid, vm, vm.CREATING, save_state=False)
                return TaskResponse(request, tid, msg=msg, vm=vm, api_view=apiview, data=self.data)
        finally:
            if err:  # Revert old status
                vm.status = old_status
                vm.save_status()

    def put(self):
        request, vm = self.request, self.vm

        # only admin
        if not (request.user and request.user.is_admin(request)):
            raise PermissionDenied

        node = vm.node
        apiview = self.apiview
        apiview['force'] = bool(ForceSerializer(data=self.data, default=False))
        queue = vm.node.fast_queue
        new_node_uuid = None
        detail_dict = {}

        if vm.status not in (vm.RUNNING, vm.STOPPED):
            raise VmIsNotOperational('VM is not stopped or running')

        if apiview['force']:
            detail_dict['force'] = True
            # final cmd and empty stdin
            cmd = 'vmadm get %s 2>/dev/null' % vm.uuid
            stdin = None
            block_key = None
            node_param = self.data.get('node')

            if node_param:
                if not request.user.is_staff:
                    raise PermissionDenied

                node = get_node(request, node_param, dc=request.dc, exists_ok=True, noexists_fail=True)

                if node.hostname == vm.node.hostname:
                    raise InvalidInput('VM already has the requested node set in DB')

                apiview['node'] = detail_dict['node'] = node.hostname
                queue = node.fast_queue
                new_node_uuid = node.uuid

        elif vm.json_changed():
            if vm.locked:
                raise VmIsLocked

            json_update = vm.json_update()
            self.check_update(json_update)

            if (vm.json_disks_changed() or vm.json_nics_changed()) and vm.tasks:
                raise VmHasPendingTasks

            # create json suitable for update
            stdin, cmd1 = self.fix_update(json_update, vm)
            self.validate_update(vm, stdin, cmd1)
            stdin = stdin.dump()

            # final cmd
            cmd = cmd1 + 'vmadm update %s >&2; e=$((e+=$?)); vmadm get %s 2>/dev/null; exit $e' % (vm.uuid, vm.uuid)

            # Possible node_image import task which will block this task on node worker
            block_key = self.node_image_import(vm.node, json_update.get('add_disks', []))

        else:  # JSON unchanged and not force
            detail = 'Successfully updated VM %s (locally)' % vm.hostname
            res = SuccessTaskResponse(request, detail, msg=LOG_VM_UPDATE, vm=vm, detail=detail)
            vm_updated.send(TaskID(res.data.get('task_id'), request=request), vm=vm)  # Signal!

            return res

        # Check compute node status after we know which compute node the task is going to be run on
        # The internal vm.node.status checking is disabled in get_vm() in __init__
        if node.status != node.ONLINE:
            raise NodeIsNotOperational

        msg = LOG_VM_UPDATE
        meta = {
            'output': {'returncode': 'returncode', 'stderr': 'message', 'stdout': 'json'},
            'replace_stderr': ((vm.uuid, vm.hostname),), 'msg': msg, 'vm_uuid': vm.uuid, 'apiview': apiview
        }
        callback = ('api.vm.base.tasks.vm_update_cb', {'vm_uuid': vm.uuid, 'new_node_uuid': new_node_uuid})

        logger.debug('Updating VM %s with json: """%s"""', vm, stdin)
        logger.debug('Update command: """%s"""', cmd)

        err = True
        vm.set_notready()

        try:
            tid, err = execute(request, vm.owner.id, cmd, stdin=stdin, meta=meta, lock=self.lock, callback=callback,
                               queue=queue, block_key=block_key)

            if err:
                return FailureTaskResponse(request, err, vm=vm)
            else:
                return TaskResponse(request, tid, msg=msg, vm=vm, api_view=apiview, data=self.data,
                                    detail_dict=detail_dict)
        finally:
            if err:
                vm.revert_notready()

    def delete(self):
        request, vm = self.request, self.vm

        # only admin
        if not (request.user and request.user.is_admin(request)):
            raise PermissionDenied

        if vm.uuid == ImageVm.get_uuid():
            raise VmIsLocked('VM is image server')

        if vm.locked:
            raise VmIsLocked

        if vm.status not in (vm.STOPPED, vm.FROZEN):
            raise VmIsNotOperational('VM is not stopped')

        if vm.tasks:
            raise VmHasPendingTasks

        apiview = self.apiview
        msg = LOG_VM_DELETE
        cmd = 'vmadm delete ' + vm.uuid
        meta = {
            'output': {'returncode': 'returncode', 'stderr': 'message'},
            'replace_text': ((vm.uuid, vm.hostname),),
            'msg': msg, 'vm_uuid': vm.uuid, 'apiview': apiview
        }
        callback = ('api.vm.base.tasks.vm_delete_cb', {'vm_uuid': vm.uuid})

        logger.debug('Deleting VM %s from compute node', vm)

        err = True
        vm.set_notready()

        try:
            tid, err = execute(request, vm.owner.id, cmd, meta=meta, lock=self.lock, expires=VM_VM_EXPIRES,
                               callback=callback, queue=vm.node.slow_queue)

            if err:
                return FailureTaskResponse(request, err, vm=vm)
            else:
                return TaskResponse(request, tid, msg=msg, vm=vm, api_view=apiview, data=self.data)
        finally:
            if err:
                vm.revert_notready()
