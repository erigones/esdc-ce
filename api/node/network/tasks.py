import json

from api.task.internal import InternalTask
from api.task.utils import mgmt_lock
from vms.models import Node
from que import TG_DC_UNBOUND
from que.tasks import cq, get_task_logger, execute

__all__ = ('create_arp_file',)

logger = get_task_logger(__name__)

ERIGONES_TASK_USER = cq.conf.ERIGONES_TASK_USER


@cq.task(name='api.node.network.tasks.create_arp_file', base=InternalTask)
@mgmt_lock(timeout=3600, key_args=(1,), wait_for_release=True)
def create_arp_file(task_id, overlay_name, **kwargs):
    """
    Task for generating ARP files for VMs connected to overlays.
    """
    arp_table = {}

    # list of nodes where overlay is defined
    overlay_nodes = [node for node in Node.objects.all()
                     if any([olay for olay in node.overlays if olay['name'] == overlay_name])]

    # go through nodes and their VMs and NICs on those VMs and add them to the ARP table
    for node in overlay_nodes:
        for olay_vm in node.vm_set.all():
            for nic in olay_vm.json_active_get_nics():
                olay_name = nic['nic_tag'].split('/')

                if len(olay_name) < 2:
                    # not an overlay nic tag
                    continue

                # if overlay name of this nic_tag is equal to the one we are generating ARP for add to table
                if olay_name[0] == overlay_name:
                    arp_table[nic['mac']] = {'arp': nic['ip'],
                                             'ip': node.get_overlay_ip(overlay_name),
                                             'port': node.get_overlay_port(overlay_name)}

    # second pass over nodes in which we write arp_table to arp files defines in overlay_rules
    for node in overlay_nodes:
        overlay_arp_file = [olay['arp_file'] for olay in node.overlays if olay['name'] == overlay_name]

        if len(overlay_arp_file) != 1:
            raise ValueError('Mutliple files returned for overlay %s', overlay_name)

        overlay_arp_file = overlay_arp_file[0]
        stdin = json.dumps(arp_table)
        cmd = 'cat /dev/stdin > %s && svcadm restart network/varpd' % overlay_arp_file
        lock = 'node %s overlay %s' % (node.uuid, overlay_name)
        tid, err = execute(ERIGONES_TASK_USER, None, cmd, stdin=stdin, callback=None, lock=lock, queue=node.fast_queue,
                           expires=300, nolog=True, tg=TG_DC_UNBOUND, ping_worker=False, check_user_tasks=False)
        if err:
            logger.error('Got error (%s) when running task %s for updating overlay ARP file %s on node %s',
                         err, tid, overlay_arp_file, node)
        else:
            logger.info('Created task %s for updating overlay ARP file %s on node %s', tid, overlay_arp_file, node)
