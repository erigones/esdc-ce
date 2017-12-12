import json
from functools import partial
from collections import namedtuple

from api.decorators import catch_exception
from api.task.internal import InternalTask
from api.task.utils import mgmt_lock
from que import TG_DC_UNBOUND
from que.tasks import cq, get_task_logger, execute
from vms.models import Node, Vm
from vms.signals import (node_created, node_json_changed, node_json_unchanged,
                         vm_created, vm_notcreated, vm_node_changed, vm_json_active_changed)

__all__ = ('node_overlay_arp_file',)

logger = get_task_logger(__name__)

ERIGONES_TASK_USER = cq.conf.ERIGONES_TASK_USER

VNIC = namedtuple('VNIC', ('node', 'mac', 'ip'))


def _is_vm_nic_over_overlay(vm_nic, overlay_rule_name=None):
    vm_nic_tag = vm_nic.get('nic_tag', '').split('/')

    if len(vm_nic_tag) == 2:
        if overlay_rule_name:
            return vm_nic_tag[0] == overlay_rule_name
        else:
            return vm_nic_tag[0]

    return False


def _get_overlay_vm_vnics(overlay_rule_name, overlay_vms):
    for vm in overlay_vms:
        for vm_nic in vm.json_active_get_nics():
            if _is_vm_nic_over_overlay(vm_nic, overlay_rule_name):
                vm_nic_mac = vm_nic.get('mac', None)
                vm_nic_ip = vm_nic.get('ip', None)

                if vm_nic_mac and vm_nic_ip:
                    yield VNIC(vm.node, vm_nic_mac, vm_nic_ip)


def _get_overlay_node_vnics(overlay_rule_name, overlay_nodes):
    for node in overlay_nodes:
        node_overlays = node.overlays

        for node_nic in node.virtual_network_interfaces.values():
            node_nic_over = node_nic.get('Host Interface', '')

            if node_nic_over in node_overlays and node_nic_over.rstrip('_0123456789') == overlay_rule_name:
                node_nic_mac = node_nic.get('MAC Address', None)
                node_nic_ip = node_nic.get('ip4addr', None)

                if node_nic_ip and node_nic_mac:
                    yield VNIC(node, node_nic_mac, node_nic_ip)


def _get_overlay_arp_table(node, overlay_rule_name, overlay_vnics):
    # dict comprehension
    return {
        vnic.mac: {
            'arp': vnic.ip,
            'port': vnic.node.get_overlay_port(overlay_rule_name),
            'ip': vnic.node.get_overlay_ip(overlay_rule_name, remote=(vnic.node.dc_name != node.dc_name)),
        }
        for vnic in overlay_vnics if vnic.node != node
    }


# noinspection PyUnusedLocal
@cq.task(name='api.node.network.tasks.node_overlay_arp_file', base=InternalTask)
@mgmt_lock(timeout=3600, key_args=(1,), wait_for_release=True)
def node_overlay_arp_file(task_id, overlay_rule_name, node_exclusive=None, **kwargs):
    """
    Task for generating ARP files for VMs and nodes connected to specific overlay.
    It is called by various signals (see below).
    """
    if node_exclusive:
        # update rules only on a specific compute node
        if node_exclusive.overlay_rules.get(overlay_rule_name, {}).get('arp_file'):
            overlay_nodes = [node_exclusive]
        else:
            return
    else:
        # list of nodes where the overlay rule is defined and uses the files search plugin
        overlay_nodes = [node for node in Node.objects.all()
                         if node.overlay_rules.get(overlay_rule_name, {}).get('arp_file')]
    # list of VM NICs (see VNIC namedtuple above) defined over the overlay
    overlay_vnics = list(_get_overlay_vm_vnics(overlay_rule_name, Vm.objects.select_related('node')
                                                                    .filter(slavevm__isnull=True,
                                                                            node__in=overlay_nodes)
                                                                    .exclude(status=Vm.NOTCREATED)))
    # Add list of Node VNICs which are defined over the overlay
    overlay_vnics += list(_get_overlay_node_vnics(overlay_rule_name, overlay_nodes))

    for node in overlay_nodes:
        # We update arp files only on online nodes
        # But we will also run this whenever node status is changed to online
        if not node.is_online():
            logger.warn('Excluding node %s from updating arp file for overlay "%s" because it is not in online state',
                        node, overlay_rule_name)
            continue

        overlay_arp_file = node.overlay_rules[overlay_rule_name]['arp_file']
        arp_table = json.dumps(_get_overlay_arp_table(node, overlay_rule_name, overlay_vnics))
        cmd = ('cat /dev/stdin > {arp_file} && '
               'chmod 0400 {arp_file} && '
               'chown netadm:netadm {arp_file} && '
               'svcadm restart network/varpd').format(arp_file=overlay_arp_file)
        lock = 'node:{node_uuid} overlay:{overlay_rule_name}'.format(node_uuid=node.uuid,
                                                                     overlay_rule_name=overlay_rule_name)
        queue = node.fast_queue

        tid, err = execute(ERIGONES_TASK_USER, None, cmd, stdin=arp_table, callback=None, lock=lock, queue=queue,
                           expires=300, nolog=True, tg=TG_DC_UNBOUND, ping_worker=False, check_user_tasks=False)
        if err:
            logger.error('Got error (%s) when running task %s for updating overlay ARP file %s on node %s',
                         err, tid, overlay_arp_file, node)
        else:
            logger.info('Created task %s for updating overlay ARP file %s on node %s', tid, overlay_arp_file, node)


# noinspection PyUnusedLocal
@catch_exception
def node_overlays_sync(sender, node=None, overlay_rules=None, skip_other_nodes=False, **kwargs):
    """
    Signal handler: create tasks for updating arp files for all overlay rules on all affected compute nodes.
    Called by node_created and node_json_changed signals with node parameter.
    Called by vm_node_overlays_sync() with node and vm_overlay_rules parameters.
    """
    assert node

    node_overlay_rules = {name for name, rule in node.overlay_rules.items() if rule.get('arp_file')}

    if overlay_rules is not None:
        node_overlay_rules = node_overlay_rules.intersection(overlay_rules)

    logger.debug('Sender "%s" (node=%s, exclusive=%s) initiated sync of overlay arp files for: %s',
                 sender, node, skip_other_nodes, node_overlay_rules)

    if skip_other_nodes:
        only_this_node = node
    else:
        only_this_node = None

    for overlay_rule in node_overlay_rules:
        task_id = node_overlay_arp_file.call(overlay_rule, node_exclusive=only_this_node)
        logger.info('Sender "%s" created task node_overlay_arp_file(%s) with task_id: %s',
                    sender, overlay_rule, task_id)


exclusive_node_overlays_sync = partial(node_overlays_sync, skip_other_nodes=True)


@catch_exception
def vm_node_overlays_sync(sender, vm=None, old_json_active=None, **kwargs):
    """
    Signal handler: create tasks for updating arp files for all overlay rules on all affected compute nodes.
    Called by vm_created, vm_node_changed, vm_json_active_changed, vm_notcreated with vm parameter.
    """
    assert vm

    vm_nics = vm.json_active_get_nics()

    if old_json_active:
        vm_nics += vm.get_nics(old_json_active)

    # List of VM related overlay rules
    vm_overlay_rules = filter(None, {_is_vm_nic_over_overlay(vm_nic) for vm_nic in vm_nics})

    if not vm_overlay_rules:
        logger.debug('Skipping node overlay sync signaled by "%s" because VM %s does not have nics on overlays',
                     sender, vm)
        return

    return node_overlays_sync(sender, node=vm.node, overlay_rules=vm_overlay_rules, **kwargs)


# erigonesd context signals:
node_created.connect(node_overlays_sync)
node_json_changed.connect(node_overlays_sync)
node_json_unchanged.connect(exclusive_node_overlays_sync)
vm_created.connect(vm_node_overlays_sync)
vm_notcreated.connect(vm_node_overlays_sync)
vm_node_changed.connect(vm_node_overlays_sync)
vm_json_active_changed.connect(vm_node_overlays_sync)
