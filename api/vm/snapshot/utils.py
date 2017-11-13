from api.exceptions import ObjectNotFound, InvalidInput, VmIsNotOperational
from vms.models import Vm, Snapshot


VM_STATUS_OPERATIONAL = frozenset([Vm.RUNNING, Vm.STOPPED, Vm.STOPPING])


def is_vm_operational(fun):
    """Decorator for checking VM status"""
    def wrap(view, vm, *args, **kwargs):
        if vm.status not in VM_STATUS_OPERATIONAL:
            raise VmIsNotOperational
        return fun(view, vm, *args, **kwargs)
    return wrap


def detail_dict(name, ser, data=None):
    """Return detail dict suitable for logging in response"""
    if data is None:
        data = ser.detail_dict()
    data['disk_id'] = ser.object.disk_id
    data[name] = ser.object.name
    return data


# noinspection PyUnusedLocal
def get_disk_id(request, vm, data=None, key='disk_id', default=1, disk_id=None):
    """Get disk_id from data and return additional disk information"""
    assert data is not None or disk_id is not None

    if disk_id is None:
        disk_id = data.get(key, default)

    # noinspection PyBroadException
    try:
        disk_id = int(disk_id)
        if not disk_id > 0:
            raise ValueError
        disk = vm.json_active_get_disks()[disk_id - 1]
        zfs_filesystem = disk['zfs_filesystem']
        real_disk_id = Snapshot.get_real_disk_id(disk)
    except Exception:
        raise InvalidInput('Invalid %s' % key)

    return disk_id, real_disk_id, zfs_filesystem


# noinspection PyUnusedLocal
def get_snapshots(request, vm, real_disk_id, data):
    """Return Snapshot queryset according to disk_id and snapshot names in data"""
    snapnames = data.get('snapnames', None)

    if not (snapnames and isinstance(snapnames, (list, tuple))):  # List and not empty
        raise InvalidInput('Invalid snapnames')

    # Stringify data, because if the name is a number, then form/data sent via socket.io is contains numbers
    snapnames = map(str, snapnames)
    # TODO: check indexes
    snaps = Snapshot.objects.select_related('vm').filter(vm=vm, disk_id=real_disk_id, name__in=snapnames)

    if not snaps:
        raise ObjectNotFound(model=Snapshot)

    return snaps, snapnames


def filter_disk_id(vm, query_filter, data, default=None):
    """Validate disk_id and update dictionary used for queryset filtering"""
    disk_id = data.get('disk_id', default)

    if disk_id is not None:
        # noinspection PyBroadException
        try:
            disk_id = int(disk_id)
            if not disk_id > 0:
                raise ValueError
            if vm:
                query_filter['disk_id'] = Snapshot.get_disk_id(vm, disk_id)
            else:
                query_filter['vm_disk_id'] = disk_id - 1
        except Exception:
            raise InvalidInput('Invalid disk_id')

    return query_filter


def filter_snap_type(query_filter, data):
    """Validate snapshot type and update dictionary used for queryset filtering"""
    stype = data.get('type', None)

    if stype:
        # noinspection PyBroadException
        try:
            stype = int(stype)
            if stype not in dict(Snapshot.TYPE):
                raise ValueError
            query_filter['type'] = stype
        except Exception:
            raise InvalidInput('Invalid snapshot type')

    return query_filter


def filter_snap_define(query_filter, data):
    """Validate snapshot definition and update dictionary used for queryset filtering"""
    define = data.get('define', None)

    if define:
        query_filter['define__name'] = define

    return query_filter


# noinspection SqlDialectInspection,SqlNoDataSourceInspection
def output_extended_snap_count(request, data):
    """Fetch extended boolean from GET request and prepare annotation dict"""
    if request.method == 'GET' and data and data.get('extended', False):
        return {'snapshots': 'SELECT COUNT(*) FROM "vms_snapshot" WHERE '
                             '"vms_snapshot"."define_id" = "vms_snapshotdefine"."id"'}
    else:
        return None


def snap_meta(vm, msg, apiview, detail):
    """Return meta dict for executing snapshot commands"""
    return {
        'output': {'returncode': 'returncode', 'stdout': 'message', 'detail': detail},
        'replace_text': ((vm.uuid, vm.hostname),),
        'msg': msg,
        'vm_uuid': vm.uuid,
        'apiview': apiview
    }


def snap_callback(vm, snap):
    """Return callback tuple for executing snapshot commands"""
    # noinspection PyRedundantParentheses
    return ('api.vm.snapshot.tasks.vm_snapshot_cb', {'vm_uuid': vm.uuid, 'snap_id': snap.pk})
