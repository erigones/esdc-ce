import json
from functools import partial
from collections import namedtuple

from api.task.internal import InternalTask
from api.task.utils import mgmt_lock
from que import TG_DC_UNBOUND
from que.tasks import cq, get_task_logger, execute
from vms.models import Node, Vm
from vms.signals import (node_created, node_json_changed, vm_created, vm_notcreated, vm_node_changed,
                         vm_json_active_changed)

__all__ = ('node_overlay_arp_file',)

logger = get_task_logger(__name__)

ERIGONES_TASK_USER = cq.conf.ERIGONES_TASK_USER

VNIC = namedtuple('VNIC', ('node', 'mac', 'ip'))


def _is_vm_nic_over_overlay(vm_nic, overlay_name=None):
    vm_nic_tag = vm_nic.get('nic_tag', '').split('/')

    if len(vm_nic_tag) == 2:
        if overlay_name:
            return vm_nic_tag[0] == overlay_name
        else:
            return True

    return False


def _get_overlay_vm_vnics(overlay_name, overlay_vms):
    for vm in overlay_vms:
        for vm_nic in vm.json_active_get_nics():
            if _is_vm_nic_over_overlay(vm_nic, overlay_name):
                vm_nic_mac = vm_nic.get('mac', None)
                vm_nic_ip = vm_nic.get('ip', None)

                if vm_nic_mac and vm_nic_ip:
                    yield VNIC(vm.node, vm_nic_mac, vm_nic_ip)


def _get_overlay_node_vnics(overlay_name, overlay_nodes):
    for node in overlay_nodes:
        node_overlays = node.overlays

        for node_nic in node.virtual_network_interfaces.values():
            node_nic_over = node_nic.get('Host Interface', '')

            # TODO: Insufficient comparison: overlay rule vs. vnic host interface
            if node_nic_over.startswith(overlay_name) and node_nic_over in node_overlays:
                node_nic_mac = node_nic.get('MAC Address', None)
                node_nic_ip = node_nic.get('ip4addr', None)

                if node_nic_ip and node_nic_mac:
                    yield VNIC(node, node_nic_mac, node_nic_ip)


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
    The ``overlay_name`` parameter is an overlay rule identifier.
    """
    # list of nodes where the overlay rule is defined and uses the files search plugin
    overlay_nodes = [node for node in Node.objects.all() if node.overlay_rules.get(overlay_name, {}).get('arp_file')]
    # list of VM NICs (see VNIC namedtuple above) defined over the overlay
    overlay_vnics = list(_get_overlay_vm_vnics(overlay_name, Vm.objects.select_related('node')
                                                               .filter(slavevm__isnull=True, node__in=overlay_nodes)
                                                               .exclude(status=Vm.NOTCREATED)))
    # Add list of Node VNICs which are defined over the overlay
    overlay_vnics += list(_get_overlay_node_vnics(overlay_name, overlay_nodes))

    for node in overlay_nodes:
        # We update arp files only on online nodes
        # But we will also run this whenever node status is changed to online
        if not node.is_online():
            logger.warn('Excluding node %s from updating arp file for overlay "%s" because it is not in online state',
                        node, overlay_name)
            continue

        overlay_arp_file = node.overlay_rules[overlay_name]['arp_file']
        arp_table = json.dumps(_get_overlay_arp_table(node, overlay_name, overlay_vnics))
        cmd = 'cat /dev/stdin > %s && chmod 0400 %s && svcadm restart network/varpd' % (overlay_arp_file,
                                                                                        overlay_arp_file)
        lock = 'node:%s overlay:%s' % (node.uuid, overlay_name)
        queue = node.fast_queue

        tid, err = execute(ERIGONES_TASK_USER, None, cmd, stdin=arp_table, callback=None, lock=lock, queue=queue,
                           expires=300, nolog=True, tg=TG_DC_UNBOUND, ping_worker=False, check_user_tasks=False)
        if err:
            logger.error('Got error (%s) when running task %s for updating overlay ARP file %s on node %s',
                         err, tid, overlay_arp_file, node)
        else:
            logger.info('Created task %s for updating overlay ARP file %s on node %s', tid, overlay_arp_file, node)


# noinspection PyUnusedLocal
def node_overlays_sync(sender, node=None, vm=None, only_if_vm_uses_overlays=False, **kwargs):
    """
    Create tasks for updating arp files for all overlay rules on all affected compute nodes.
    Called by node_created and node_json_changed signals with node parameter.
    Called by vm_created, vm_node_changed, vm_json_active_changed, vm_notcreated with vm parameter.
    """
    if vm:
        if only_if_vm_uses_overlays and not any(_is_vm_nic_over_overlay(vnic) for vnic in vm.json_active_get_nics()):
            logger.info('Skipping node overlay sync signaled by "%s" because VM %s does not have nics on overlays',
                        sender, vm)
            return

        node = vm.node

    for overlay_rule in node.overlay_rules.keys():
        task_id = node_overlay_arp_file.call(overlay_rule)
        logger.info('Sender "%s" created task node_overlay_arp_file(%s) with task_id: %s',
                    sender, overlay_rule, task_id)


vm_node_overlay_sync = partial(node_overlays_sync, only_if_vm_uses_overlays=True)


# erigonesd context signals:
node_created.connect(node_overlays_sync)
node_json_changed.connect(node_overlays_sync)
vm_created.connect(vm_node_overlay_sync)
vm_notcreated.connect(node_overlays_sync)  # TODO: cannot check for overlays, because we don't know if VM used overlays
vm_node_changed.connect(vm_node_overlay_sync)
vm_json_active_changed.connect(node_overlays_sync)  # TODO: cannot check for overlays, because -||-
