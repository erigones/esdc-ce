import json
from collections import namedtuple

from api.task.internal import InternalTask
from api.task.utils import mgmt_lock
from que import TG_DC_UNBOUND
from que.tasks import cq, get_task_logger, execute
from vms.models import Node, Vm

__all__ = ('node_overlay_arp_file',)

logger = get_task_logger(__name__)

ERIGONES_TASK_USER = cq.conf.ERIGONES_TASK_USER

VNIC = namedtuple('VNIC', ('node', 'mac', 'ip'))


def _get_overlay_vnics(overlay_name, overlay_vms):
    for vm in overlay_vms:
        for vm_nic in vm.json_active_get_nics():
            vm_nic_tag = vm_nic.get('nic_tag', '').split('/')

            if len(vm_nic_tag) == 2 and vm_nic_tag[0] == overlay_name:
                vm_nic_mac = vm_nic.get('mac', '')
                vm_nic_ip = vm_nic.get('ip', '')

                if vm_nic_mac and vm_nic_ip:
                    yield VNIC(vm.node, vm_nic_mac, vm_nic_ip)


def _get_overlay_arp_table(node, overlay_name, overlay_vnics):
    # dict comprehension
    return {
        vnic.mac: {
            'arp': vnic.ip,
            'port': vnic.node.get_overlay_port(overlay_name),
            'ip': vnic.node.get_overlay_ip(overlay_name, remote=(vnic.node.dc_name != node.dc_name)),
        }
        for vnic in overlay_vnics if vnic.node != node
    }


# noinspection PyUnusedLocal
@cq.task(name='api.node.network.tasks.node_overlay_arp_file', base=InternalTask)
@mgmt_lock(timeout=3600, key_args=(1,), wait_for_release=True)
def node_overlay_arp_file(task_id, overlay_name, **kwargs):
    """
    Task for generating ARP files for VMs connected to overlays.
    """
    # list of nodes where the overlay rule is defined and uses the files search plugin
    overlay_nodes = [node for node in Node.objects.all() if node.overlay_rules.get(overlay_name, {}).get('arp_file')]
    # list of VM NICs (see VNIC namedtuple above) defined over the overlay
    overlay_vnics = list(_get_overlay_vnics(overlay_name, Vm.objects.select_related('node')
                                                            .filter(slavevm__isnull=True, node__in=overlay_nodes)
                                                            .exclude(status=Vm.NOTCREATED)))

    for node in overlay_nodes:
        overlay_arp_file = node.overlay_rules[overlay_name]['arp_file']
        arp_table = json.dumps(_get_overlay_arp_table(node, overlay_name, overlay_vnics))
        cmd = 'cat /dev/stdin > %s && svcadm restart network/varpd' % overlay_arp_file
        lock = 'node %s overlay %s' % (node.uuid, overlay_name)
        queue = node.fast_queue

        tid, err = execute(ERIGONES_TASK_USER, None, cmd, stdin=arp_table, callback=None, lock=lock, queue=queue,
                           expires=300, nolog=True, tg=TG_DC_UNBOUND, ping_worker=False, check_user_tasks=False)
        if err:
            logger.error('Got error (%s) when running task %s for updating overlay ARP file %s on node %s',
                         err, tid, overlay_arp_file, node)
        else:
            logger.info('Created task %s for updating overlay ARP file %s on node %s', tid, overlay_arp_file, node)
