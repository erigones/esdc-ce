from vms.models import NodeStorage, Snapshot, Backup, Node
from que.tasks import cq, get_task_logger
from que.mgmt import MgmtCallbackTask
from que.exceptions import TaskException
from api.task.utils import callback
from api.task.tasks import task_log_cb_success
from api.vm.snapshot.tasks import t_long, parse_node_snaps, sync_snapshots
from api.node.snapshot.api_views import NodeVmSnapshotList
from api.vm.backup.utils import sync_backups

__all__ = ('node_vm_snapshot_sync_cb', 'node_vm_snapshot_sync_all')

logger = get_task_logger(__name__)


@cq.task(name='api.node.snapshot.tasks.node_vm_snapshot_sync_cb', base=MgmtCallbackTask, bind=True)
@callback()
def node_vm_snapshot_sync_cb(result, task_id, nodestorage_id=None):
    """
    A callback function for PUT api.node.snapshot.views.node_vm_snapshot_list a.k.a. node_vm_snapshot_sync.
    """
    ns = NodeStorage.objects.select_related('node', 'storage').get(id=nodestorage_id)
    node = ns.node
    data = result.pop('data', '')

    if result['returncode'] != 0:
        msg = result.get('message', '') or data
        logger.error('Found nonzero returncode in result from PUT node_vm_snapshot_list(%s@%s). Error: %s',
                     ns.zpool, node.hostname, msg)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], msg))

    node_snaps = parse_node_snaps(data)
    logger.info('Found %d snapshots on node storage %s@%s', len(node_snaps), ns.zpool, node.hostname)
    ns_snaps = ns.snapshot_set.select_related('vm').all()
    lost = sync_snapshots(ns_snaps, node_snaps)

    # Remaining snapshots on compute node are internal or old lost snapshots which do not exist in DB
    # or replicated snapshots. Let's count all the remaining es- and as- snapshots sizes as replicated snapshots
    snap_prefix = Snapshot.USER_PREFIX
    rep_snaps_size = sum(t_long(node_snaps.pop(snap)[1]) for snap in tuple(node_snaps.keys())
                         if snap.startswith(snap_prefix))
    ns.set_rep_snapshots_size(rep_snaps_size)

    # The internal snapshots also include dataset backups on a backup node
    if node.is_backup:
        node_bkps = ns.backup_set.select_related('node', 'vm').filter(type=Backup.DATASET)
        lost_bkps = sync_backups(node_bkps, node_snaps)
    else:
        lost_bkps = 0

    logger.info('Node storage %s@%s has %s bytes of replicated snapshots', ns.zpool, node.hostname, rep_snaps_size)
    logger.info('Node storage %s@%s has following internal/service snapshots: %s',
                ns.zpool, node.hostname, node_snaps.keys())
    # Recalculate snapshot counters for all DCs
    ns.save(update_resources=True, update_dcnode_resources=True, recalculate_vms_size=False,
            recalculate_snapshots_size=True, recalculate_images_size=False, recalculate_backups_size=False,
            recalculate_dc_snapshots_size=ns.dc.all())

    # Remove cached snapshot sum for each VM:
    for vm_uuid in ns_snaps.values_list('vm__uuid', flat=True).distinct():
        Snapshot.clear_total_vm_size(vm_uuid)

    if not result['meta'].get('internal'):
        msg = 'Snapshots successfully synced'
        if lost:
            msg += '; WARNING: %d snapshot(s) lost' % lost
        if lost_bkps:
            msg += '; WARNING: %d backup(s) lost' % lost_bkps

        result['message'] = msg
        task_log_cb_success(result, task_id, obj=ns, **result['meta'])

    return result


@cq.task(name='api.node.snapshot.tasks.node_vm_snapshot_sync_all')
def node_vm_snapshot_sync_all():
    """
    This is a periodic beat task responsible for syncing node snapshot sizes of all VMs on a compute node.
    """
    for node in Node.all():
        if node.is_online() and (node.is_compute or node.is_backup):
            try:
                NodeVmSnapshotList.sync(node)
            except Exception as exc:
                logger.exception(exc)
