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
module: pcs_auth
short_description: Module for interacting with 'pcs auth'
description:
  - module for authenticating nodes in pacemaker cluster using 'pcs auth' for RHEL/CentOS.
version_added: "2.4"
options:
  state:
    description:
    - "'present' authenticates the node while 'absent' will remove the node authentification"
    - "node from which this is run is (de)authenticated agains the node specified in 'node_name'"
    required: false
    default: present
    choices: [ 'present', 'absent' ]
  node_name:
    description:
      - hostname of node for authentication
    required: true
  username:
    description:
      - "username of 'cluster user' for cluster authentication"
    required: false
    default: 'hacluster'
  password:
    description:
      - "password of 'cluster user' for cluster authentication"
    required: false
notes:
  - This module is (de)authenticating nodes only 1-way == authenticating node 1 agains
    node 2 doesn't mean that node 2 is authenticated agains node 1!
  - Tested on CentOS 6.8, 7.3
  - Tested on Red Hat Enterprise Linux 7.3, 7.4, 7.6
  - Experimental support for Red Hat Enterprise Linux 8.0 Beta and pcs 0.10
'''

EXAMPLES = '''
- name: Authorize node 'n1' with default user 'hacluster' and password 'testtest'
  pcs_auth:
    node_name: 'n1'
    password: 'testtest'

- name: authorize all nodes in ansible play to each other
  pcs_auth:
    node_name: "{{ hostvars[item]['ansible_hostname'] }}"
    password: 'testtest'
  with_items: "{{ play_hosts }}"

- name: de-authorize all nodes from each other in ansible play
  pcs_auth:
    node_name: "{{  hostvars[item]['ansible_hostname'] }}"
    state: 'absent'
  with_items: "{{ play_hosts }}"

'''

import os.path
import json
from distutils.spawn import find_executable

from ansible.module_utils.basic import AnsibleModule


def run_module():
        module = AnsibleModule(
            argument_spec=dict(
                state=dict(default="present", choices=['present', 'absent']),
                node_name=dict(required=True),
                username=dict(required=False, default="hacluster"),
                password=dict(required=False, no_log=True)
            ),
            supports_check_mode=True
        )

        state = module.params['state']
        node_name = module.params['node_name']

        if state == 'present' and not module.params['password']:
            module.fail_json(msg="Missing password parameter needed for authorizing the node")

        result = {}

        if find_executable('pcs') is None:
            module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")

        # get the pcs major.minor version
        rc, out, err = module.run_command('pcs --version')
        if rc == 0:
            pcs_version = out.split('.')[0] + '.' + out.split('.')[1]
        else:
            module.fail_json(msg="pcs --version exited with non-zero exit code (" + rc + "): " + out + error)

        if os.path.isfile('/var/lib/pcsd/tokens') and pcs_version == '0.9':
            tokens_file = open('/var/lib/pcsd/tokens', 'r+')
            # load JSON tokens
            tokens_data = json.load(tokens_file)
            result['tokens_data'] = tokens_data['tokens']
        if os.path.isfile('/var/lib/pcsd/known-hosts') and pcs_version == '0.10':
            tokens_file = open('/var/lib/pcsd/known-hosts', 'r+')
            # load JSON tokens
            tokens_data = json.load(tokens_file)
            result['tokens_data'] = tokens_data['known_hosts']

        rc, out, err = module.run_command('pcs cluster pcsd-status %(node_name)s' % module.params)

        if state == 'present' and rc != 0:
            # WARNING: this will also consider nodes to which we cannot connect as unauthorized
            result['changed'] = True
            if not module.check_mode:
                if pcs_version == '0.9':
                    cmd_auth = 'pcs cluster auth %(node_name)s -u %(username)s -p %(password)s --local' % module.params
                elif pcs_version == '0.10':
                    cmd_auth = 'pcs host auth %(node_name)s -u %(username)s -p %(password)s' % module.params
                else:
                    module.fail_json(msg="unsupported version of pcs (" + pcs_version + "). Only versions 0.9 and 0.10 are supported.")
                rc, out, err = module.run_command(cmd_auth)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to authenticate node using command '" + cmd_auth + "'", output=out, error=err)

        elif (state == 'absent' and tokens_data and (
                (pcs_version == '0.9' and node_name in tokens_data['tokens']) or
                (pcs_version == '0.10' and node_name in tokens_data['known_hosts'])
                )):
            result['changed'] = True
            if not module.check_mode:
                if pcs_version == '0.9':
                    del tokens_data['tokens'][node_name]
                    del tokens_data['ports'][node_name]
                    tokens_data['data_version'] += 1
                    # write the change into token file
                    tokens_file.seek(0)
                    json.dump(tokens_data, tokens_file, indent=4)
                    tokens_file.truncate()
                elif pcs_version == '0.10':
                    cmd_deauth = 'pcs host deauth %(node_name)s' % module.params
                    rc, out, err = module.run_command(cmd_deauth)
                    if rc == 0:
                        module.exit_json(**result)
                    else:
                        module.fail_json(msg="Failed to de-authenticate node using command '" + cmd_deauth + "'", output=out, error=err)
                else:
                    module.fail_json(msg="unsupported version of pcs (" + pcs_version + "). Only versions 0.9 and 0.10 are supported.")

        else:
            result['changed'] = False
            module.exit_json(**result)

        # END of module
        module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
