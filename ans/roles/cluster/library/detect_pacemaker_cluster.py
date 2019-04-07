#!/usr/bin/python
# Copyright: (c) 2018, Ondrej Famera <ondrej-xa2iel8u@famera.cz>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
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
module: detect_pacemaker_cluster
author: "Ondrej Famera (@ondrejHome)"
short_description: detect facts about installed pacemaker cluster
description:
     - Module for collecting various information about pacemaker cluster
version_added: "2.4"
notes:
   - Tested on CentOS 7.5
   - works only with pacemaker clusters that uses /etc/corosync/corosync.conf
requirements: [ ]
'''

EXAMPLES = '''
- detect_pacemaker_cluster

'''

import re
from ansible.module_utils.basic import AnsibleModule


def run_module():
        module = AnsibleModule(
            argument_spec=dict(),
            supports_check_mode=True
        )

        result = {}

        try:
            corosync_conf = open('/etc/corosync/corosync.conf', 'r')
            nodes = re.compile(r"node\s*\{([^}]+)\}", re.M + re.S)
            nodes_list = nodes.findall(corosync_conf.read())
            node_list_set = set()
            if len(nodes_list) > 0:
                n_name = re.compile(r"ring0_addr\s*:\s*([\w.-]+)\s*", re.M)
                for node in nodes_list:
                    n_name2 = None
                    n_name2 = n_name.search(node)
                    if n_name2:
                        node_name = n_name2.group(1)
                        node_list_set.add(node_name.rstrip())

            result['ansible_facts'] = {}
            result['ansible_facts']['pacemaker_detected_cluster_nodes'] = node_list_set
            result['ansible_facts']['pacemaker_cluster_present'] = True
        except IOError as e:
            result['ansible_facts'] = {}
            result['ansible_facts']['pacemaker_cluster_present'] = False
        module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
