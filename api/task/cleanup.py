from api.task.signals import task_cleanup_signal


# noinspection PyUnusedLocal,PyProtectedMember
def _task_cleanup(result, task_id, task_status, obj, **kwargs):
    """
    Cleanup after task is revoked.
    """
    apiview = result['meta']['apiview']
    view = apiview['view']

    if view == 'vm_snapshot':
        from vms.models import Vm, Snapshot
        from api.vm.snapshot.tasks import _vm_snapshot_cb_failed

        if apiview['method'] == 'PUT' and 'source_hostname' in apiview:
            vm = Vm.objects.get(hostname=apiview['source_hostname'])
        else:
            vm = obj

        snap = Snapshot.objects.get(vm=vm, disk_id=Snapshot.get_disk_id(vm, apiview['disk_id']),
                                    name=apiview['snapname'])
        _vm_snapshot_cb_failed(result, task_id, snap, apiview['method'], vm=obj)

    elif view == 'vm_snapshot_list':
        from vms.models import Snapshot
        from api.vm.snapshot.tasks import _vm_snapshot_list_cb_failed

        snaps = Snapshot.objects.filter(vm=obj, disk_id=Snapshot.get_disk_id(obj, apiview['disk_id']),
                                        name__in=apiview['snapnames'])
        _vm_snapshot_list_cb_failed(result, task_id, snaps, apiview['method'])

    elif view == 'vm_backup':
        from vms.models import Backup
        from api.vm.backup.tasks import _vm_backup_cb_failed

        bkp = Backup.objects.get(vm_hostname=apiview['hostname'], vm_disk_id=apiview['disk_id'] - 1,
                                 name=apiview['bkpname'])
        _vm_backup_cb_failed(result, task_id, bkp, apiview['method'], vm=obj)

    elif view == 'vm_backup_list':
        from vms.models import Backup
        from api.vm.backup.tasks import _vm_backup_list_cb_failed

        bkps = Backup.objects.filter(vm_hostname=apiview['hostname'], vm_disk_id=apiview['disk_id'] - 1,
                                     name__in=apiview['bkpnames'])
        _vm_backup_list_cb_failed(result, task_id, bkps, apiview['method'])

    elif view == 'vm_manage':
        if apiview['method'] == 'POST':
            from api.vm.base.tasks import _vm_create_cb_failed
            result['message'] = ''
            _vm_create_cb_failed(result, task_id, obj)
        elif apiview['method'] == 'DELETE':
            from api.vm.base.tasks import _vm_delete_cb_failed
            _vm_delete_cb_failed(result, task_id, obj)
        elif apiview['method'] == 'PUT':
            from api.vm.base.tasks import _vm_update_cb_done
            _vm_update_cb_done(result, task_id, obj)

    elif view == 'vm_status':
        from api.vm.status.tasks import _vm_status_cb_failed

        if apiview['method'] == 'PUT':
            _vm_status_cb_failed(result, task_id, obj)

    elif view == 'vm_migrate':
        from vms.models import SlaveVm
        from api.vm.migrate.tasks import _vm_migrate_cb_failed

        ghost_vm = SlaveVm.get_by_uuid(obj.slave_vms[0])
        assert ghost_vm.is_used_for_migration()
        _vm_migrate_cb_failed(result, task_id, obj, ghost_vm)

    elif view == 'image_manage' or view == 'image_snapshot':
        # obj = Image
        from vms.models import Snapshot
        from api.image.base.tasks import _image_manage_cb_failed

        method = apiview['method']
        snap_id = obj.src_snap_id

        if method == 'POST' and snap_id:
            snap = Snapshot.objects.get(id=snap_id)
        else:
            snap = None

        _image_manage_cb_failed(result, task_id, obj, method, snap=snap)

    elif view == 'node_image':
        # obj = NodeStorage
        from vms.models import Image
        from api.node.image.tasks import _node_image_cb_failed

        img = Image.objects.get(name=apiview['name'])
        _node_image_cb_failed(result, task_id, obj, img)

    else:
        task_cleanup_signal.send(sender=view, apiview=apiview, result=result, task_id=task_id, status=task_status,
                                 obj=obj)


def task_cleanup(result, task_id, task_status, obj=None, **kwargs):
    """
    Emergency cleanup (run instead of callback).
    """
    _task_cleanup(result, task_id, task_status, obj, **kwargs)
