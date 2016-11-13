from que.tasks import execute
from vms.models import SnapshotDefine, Snapshot, BackupDefine, Backup, IPAddress
from core.celery.config import ERIGONES_TASK_USER


def is_vm_missing(vm, msg):
    """
    Check failed command output and return True if VM is not on compute node.
    """
    check_str = vm.hostname + ': No such zone configured'

    return check_str in msg


def vm_delete_snapshots_of_removed_disks(vm):
    """
    This helper function deletes snapshots for VM with changing disk IDs. Bug #chili-363
    ++ Bug #chili-220 - removing snapshot and backup definitions for removed disks.
    """
    removed_disk_ids = [Snapshot.get_real_disk_id(i) for i in vm.create_json_update_disks().get('remove_disks', [])]
    if removed_disk_ids:
        Snapshot.objects.filter(vm=vm, disk_id__in=removed_disk_ids).delete()
        SnapshotDefine.objects.filter(vm=vm, disk_id__in=removed_disk_ids).delete()
        Backup.objects.filter(vm=vm, disk_id__in=removed_disk_ids, last=True).update(last=False)
        BackupDefine.objects.filter(vm=vm, disk_id__in=removed_disk_ids).delete()
    return removed_disk_ids


def vm_update_ipaddress_usage(vm):
    """
    This helper function is responsible for updating IPAddress.usage and IPAddress.vm of server IPs (#chili-615,1029),
    by removing association from IPs that, are not set on any NIC and:
        - when a VM is deleted all IP usages are set to IPAddress.VM (in DB) and
        - when a VM is created or updated all IP usages are set to IPAddress.VM_REAL (on hypervisor) and

    Always call this function _only_ after vm.json_active is synced with vm.json!!!
    """
    current_ips = set(vm.json_active_get_ips())
    current_ips.update(vm.json_get_ips())
    # Return old IPs back to IP pool, so they can be used again
    vm.ipaddress_set.exclude(ip__in=current_ips).update(vm=None, usage=IPAddress.VM)

    if vm.is_notcreated():
        # Server was deleted from hypervisor
        vm.ipaddress_set.filter(usage=IPAddress.VM_REAL).update(usage=IPAddress.VM)
    else:
        # Server was updated or created
        vm.ipaddress_set.filter(usage=IPAddress.VM).update(usage=IPAddress.VM_REAL)


def vm_deploy(vm, force_stop=False):
    """
    Internal API call used for finishing VM deploy;
    Actually cleaning the json and starting the VM.
    """
    if force_stop:  # VM is running without OS -> stop
        cmd = 'vmadm stop %s -F >/dev/null 2>/dev/null; vmadm get %s 2>/dev/null' % (vm.uuid, vm.uuid)
    else:  # VM is stopped and deployed -> start
        cmd = 'vmadm start %s >/dev/null 2>/dev/null; vmadm get %s 2>/dev/null' % (vm.uuid, vm.uuid)

    msg = 'Deploy server'
    lock = 'vmadm deploy ' + vm.uuid
    meta = {
        'output': {
            'returncode': 'returncode',
            'stderr': 'message',
            'stdout': 'json'
        },
        'replace_stderr': ((vm.uuid, vm.hostname),),
        'msg': msg, 'vm_uuid': vm.uuid
    }
    callback = ('api.vm.base.tasks.vm_deploy_cb', {'vm_uuid': vm.uuid})

    return execute(ERIGONES_TASK_USER, None, cmd, meta=meta, lock=lock, callback=callback,
                   queue=vm.node.fast_queue, nolog=True, ping_worker=False, check_user_tasks=False)


def vm_reset(vm):
    """
    Internal API call used for VM reboots in emergency situations.
    """
    cmd = 'vmadm stop %s -F; vmadm start %s' % (vm.uuid, vm.uuid)
    return execute(ERIGONES_TASK_USER, None, cmd, callback=False, queue=vm.node.fast_queue, nolog=True,
                   check_user_tasks=False)
