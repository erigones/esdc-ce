#!/usr/bin/python
# Copyright: (c) 2018, Ondrej Famera <ondrej-xa2iel8u@famera.cz>
# GNU General Public License v3.0+ (see LICENSE-GPLv3.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# Apache License v2.0 (see LICENSE-APACHE2.txt or http://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
author: "Ondrej Famera (@OndrejHome)"
module: pcs_cluster
short_description: "wrapper module for 'pcs cluster setup/destroy/node add/node remove'"
description:
  - "module for creating/destroying/extending/shrinking clusters using 'pcs' utility"
version_added: "2.4"
options:
  state:
    description:
      - "'present' - ensure that cluster exists"
      - "'absent' - ensure cluster doesn't exist"
    required: false
    default: present
    choices: ['present', 'absent']
  node_list:
    description:
      - space separated list of nodes in cluster
    required: false
  cluster_name:
    description:
      - pacemaker cluster name
    required: true
  token:
    description:
      - sets time in milliseconds until a token loss is declared after not receiving a token
    required: false
  transport:
    description:
      - "'default' - use default transport protocol ('udp' in CentOS/RHEL 6, 'udpu' in CentOS/RHEL 7), 'knet' in Fedora 29"
      - "'udp' - use UDP multicast protocol"
      - "'udpu' - use UDP unicast protocol"
      - "'knet' - use KNET protocol"
    required: false
    default: default
    choices: ['default', 'udp', 'udpu', 'knet']
  allowed_node_changes:
    description:
      - "'none' - node list must match existing cluster if cluster should be present"
      - "'add' - allow adding new nodes to cluster"
      - "'remove' - allow removing nodes from cluster"
    default: none
    required: false
    choices: ['none', 'add', 'remove']
notes:
   - Tested on CentOS 6.8, 6.9, 7.3, 7.4, 7.5
   - Tested on Red Hat Enterprise Linux 7.3, 7.4, 7.6
   - Experimental support on Fedora 29 with pcs-0.10
   - "When adding/removing nodes, make sure to use 'run_once=True' and 'delegate_to' that points to
     node that will stay in cluster, nodes cannot add themselves to cluster and node that removes
     themselves may not remove all needed cluster information
     - https://bugzilla.redhat.com/show_bug.cgi?id=1360882"
'''

EXAMPLES = '''
- name: Setup cluster
  pcs_cluster:
    node_list: "{% for item in play_hosts %}{{ hostvars[item]['ansible_hostname'] }} {% endfor %}"
    cluster_name: 'test-cluster'
  run_once: True

- name: Create cluster with totem token timeout of 5000 ms and UDP unicast transport protocol
  pcs_cluster:
    node_list: "{% for item in play_hosts %}{{ hostvars[item]['ansible_hostname'] }} {% endfor %}"
    cluster_name: 'test-cluster'
    token: 5000
    transport: 'udpu'
  run_once: True

- name: Create cluster with redundant corosync links
  pcs_cluster:
    cluster_name: 'test-cluster'
    node_list: >
      node1-eth0.example.com,node1-eth1.example.com
      node2-eth0.example.com,node2-eth1.example.com
    state: 'present'
  run_once: True

- name: Add new nodes to existing cluster
  pcs_cluster:
    node_list: 'existing-node-1 existing-node-2 new-node-3 new-node-4'
    cluster_name: 'test-cluster'
    allowed_node_changes: 'add'
  run_once: True
  delegate_to: existing-node-1

- name: Remove nodes from existing cluster cluster (test-cluster= exiting-node-1, exiting-node-2, exiting-node-3, exiting-node-4)
  pcs_cluster:
    node_list: 'existing-node-1 existing-node-2'
    cluster_name: 'test-cluster'
    allowed_node_changes: 'remove'
  run_once: True
  delegate_to: existing-node-1

- name: Destroy cluster on each node
  pcs_cluster:
    state: 'absent'
'''

import os.path
import re
from distutils.spawn import find_executable

from ansible.module_utils.basic import AnsibleModule


def run_module():
        module = AnsibleModule(
            argument_spec=dict(
                state=dict(default="present", choices=['present', 'absent']),
                node_list=dict(required=False),
                cluster_name=dict(required=False),
                token=dict(required=False, type='int'),
                transport=dict(required=False, default="default", choices=['default', 'udp', 'udpu', 'knet']),
                allowed_node_changes=dict(required=False, default="none", choices=['none', 'add', 'remove']),
            ),
            supports_check_mode=True
        )

        state = module.params['state']
        allowed_node_changes = module.params['allowed_node_changes']
        node_list = module.params['node_list']
        if state == 'present' and (not module.params['node_list'] or not module.params['cluster_name']):
            module.fail_json(msg='When creating/expanding/shrinking cluster you must specify both node_list and cluster_name')
        result = {}

        if find_executable('pcs') is None:
            module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")

        # get the pcs major.minor version
        rc, out, err = module.run_command('pcs --version')
        if rc == 0:
            pcs_version = out.split('.')[0] + '.' + out.split('.')[1]
        else:
            module.fail_json(msg="pcs --version exited with non-zero exit code (" + rc + "): " + out + error)

        # /var/lib/pacemaker/cib/cib.xml exists on cluster that were at least once started
        cib_xml_exists = os.path.isfile('/var/lib/pacemaker/cib/cib.xml')
        # EL 6 configuration file
        cluster_conf_exists = os.path.isfile('/etc/cluster/cluster.conf')
        # EL 7 configuration file
        corosync_conf_exists = os.path.isfile('/etc/corosync/corosync.conf')

        if node_list is None:
            node_list_set = set()
        else:
            node_list_set = set(node_list.split())
        detected_node_list_set = set()
        if corosync_conf_exists:
            try:
                corosync_conf = open('/etc/corosync/corosync.conf', 'r')
                nodes = re.compile(r"node\s*\{([^}]+)\}", re.M + re.S)
                re_nodes_list = nodes.findall(corosync_conf.read())
                re_node_list_set = set()
                if len(re_nodes_list) > 0:
                    n_name = re.compile(r"ring[0-9]+_addr\s*:\s*([\w.-]+)\s*", re.M)
                    for node in re_nodes_list:
                        rings = None
                        rings = n_name.findall(node)
                        if rings:
                            re_node_list_set.add(','.join(rings))

                detected_node_list_set = re_node_list_set
            except IOError as e:
                detected_node_list_set = set()

        # if there is no cluster configuration and cluster should be created do 'pcs cluster setup'
        if state == 'present' and not (cluster_conf_exists or corosync_conf_exists or cib_xml_exists):
            result['changed'] = True
            # create cluster from node list that was provided to module
            if pcs_version == '0.9':
                module.params['token_param'] = '' if (not module.params['token']) else '--token %(token)s' % module.params
                module.params['transport_param'] = '' if (module.params['transport'] == 'default') else '--transport %(transport)s' % module.params
                cmd = 'pcs cluster setup --name %(cluster_name)s %(node_list)s %(token_param)s %(transport_param)s' % module.params
            elif pcs_version == '0.10':
                module.params['token_param'] = '' if (not module.params['token']) else 'token %(token)s' % module.params
                module.params['transport_param'] = '' if (module.params['transport'] == 'default') else 'transport %(transport)s' % module.params
                cmd = 'pcs cluster setup %(cluster_name)s %(node_list)s %(token_param)s %(transport_param)s' % module.params
            else:
                module.fail_json(msg="unsupported version of pcs (" + pcs_version + "). Only versions 0.9 and 0.10 are supported.")
            if not module.check_mode:
                rc, out, err = module.run_command(cmd)
                if rc == 0:
                    module.exit_json(changed=True)
                else:
                    module.fail_json(msg="Failed to create cluster using command '" + cmd + "'", output=out, error=err)
        # if cluster exists and we are allowed to add/remove nodes do 'pcs cluster node add/remove'
        elif state == 'present' and corosync_conf_exists and allowed_node_changes != 'none' and node_list_set != detected_node_list_set:
            result['changed'] = True
            result['detected_nodes'] = detected_node_list_set
            # adding new nodes to cluster
            if allowed_node_changes == 'add':
                result['nodes_to_add'] = node_list_set - detected_node_list_set
                for node in (node_list_set - detected_node_list_set):
                    cmd = 'pcs cluster node add ' + node
                    if not module.check_mode:
                        rc, out, err = module.run_command(cmd)
                        if rc == 0:
                            module.exit_json(changed=True)
                        else:
                            module.fail_json(msg="Failed to add node '" + node + "' to cluster using command '" + cmd + "'", output=out, error=err)
            # removing nodes from cluster
            if allowed_node_changes == 'remove':
                result['nodes_to_remove'] = detected_node_list_set - node_list_set
                for node in (detected_node_list_set - node_list_set):
                    cmd = 'pcs cluster node remove ' + node
                    if not module.check_mode:
                        rc, out, err = module.run_command(cmd)
                        if rc == 0:
                            module.exit_json(changed=True)
                        else:
                            module.fail_json(msg="Failed to remove node '" + node + "' from cluster using command '" + cmd + "'", output=out, error=err)
        # if cluster should be removed and cluster configuration exists
        elif state == 'absent' and (cluster_conf_exists or corosync_conf_exists or cib_xml_exists):
            result['changed'] = True
            # destroy cluster on node where this module is executed
            cmd = 'pcs cluster destroy'
            if not module.check_mode:
                rc, out, err = module.run_command(cmd)
                if rc == 0:
                    module.exit_json(changed=True)
                else:
                    module.fail_json(msg="Failed to delete cluster using command '" + cmd + "'", output=out, error=err)
        # if cluster doesn't exists and should be removed, just acknowledge that no chage is needed
        elif state == 'absent' and (not cluster_conf_exists and not corosync_conf_exists and not cib_xml_exists):
            module.exit_json(changed=False, msg="No change needed, cluster is not present.")
        # if the cluster looks as it should
        elif state == 'present' and corosync_conf_exists and node_list_set == detected_node_list_set:
            module.exit_json(changed=False, msg="No change needed, cluster is present.")
        # if requested node list and detected node list are different but we are not allowed to change, fail
        elif state == 'present' and corosync_conf_exists and allowed_node_changes == 'none' and node_list_set != detected_node_list_set:
            module.fail_json(msg="'Detected node list' and 'Requested node list' are different, but changes are not allowed.")
        else:
            # all other cases, possibly also unhadled ones
            module.exit_json(changed=False)

        # END of module
        module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
