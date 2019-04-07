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
module: pcs_property
short_description: "wrapper module for 'pcs property'"
description:
  - "module for setting and unsetting cluster and node properties using 'pcs' utility"
version_added: "2.4"
options:
  state:
    description:
      - "'present' - ensure that cluster property exists with given value"
      - "'absent' - ensure cluster property doesn't exist (is unset)"
    required: false
    default: present
    choices: ['present', 'absent']
  name:
    description:
      - name of cluster property
    required: true
  node:
    description:
      - node name for node-specific property
    required: false
  value:
    description:
      - value of cluster property
    required: false
  cib_file:
    description:
      - "Apply changes to specified file containing cluster CIB instead of running cluster."
    required: false
notes:
   - Tested on CentOS 7.3, Fedora 28, 29
   - Tested on Red Hat Enterprise Linux 7.6
   - node property values with spaces are not idempotent
'''

EXAMPLES = '''
- name: set maintenance mode cluster property (enable maintenance mode)
  pcs_property:
    name: 'maintenance-mode'
    value: 'true'

- name: unset maintenance mode cluster property (disable maintenance mode)
  pcs_property:
    name: 'maintenance-mode'
    state: 'absent'

- name: set property 'standby' to 'on' for node 'node-1' (standby node-1)
  pcs_property:
    name: 'standby'
    node: 'node-1'
    value: 'on'

- name: remove 'standby' node attribute from 'node-1' (unstandby node-1)
  pcs_property:
    name: 'standby'
    node: 'node-1'
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
                name=dict(required=True),
                node=dict(required=False),
                value=dict(required=False),
                cib_file=dict(required=False),
            ),
            supports_check_mode=True
        )

        state = module.params['state']
        name = module.params['name']
        value = module.params['value']
        node = module.params['node']
        cib_file = module.params['cib_file']

        result = {}

        if find_executable('pcs') is None:
            module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")

        if state == 'present' and value is None:
            module.fail_json(msg="To set property 'value' must be specified.")

        module.params['cib_file_param'] = ''
        if cib_file is not None and os.path.isfile(cib_file):
            module.params['cib_file_param'] = '-f ' + cib_file

        # get property list from running cluster
        rc, out, err = module.run_command('pcs %(cib_file_param)s property show' % module.params)
        properties = {}
        if rc == 0:
            # indicator in which part of parsing we are
            property_type = None
            properties['cluster'] = {}
            properties['node'] = {}
            # we are stripping last line as they doesn't contain properties
            for row in out.split('\n')[0:-1]:
                # based on row we see the section to either cluster or node properties
                if row == 'Cluster Properties:':
                    property_type = 'cluster'
                elif row == 'Node Attributes:':
                    property_type = 'node'
                else:
                    # when identifier of section is not preset we are at the property
                    tmp = row.lstrip().split(':')
                    if property_type == 'cluster':
                        properties['cluster'][tmp[0]] = tmp[1].lstrip()
                    elif property_type == 'node':
                        properties['node'][tmp[0]] = {}
                        # FIXME: this matches only properties which values doesn't contain spaces
                        match_node_properties = re.compile(r"(\w+=\w+)\s*")
                        matched_properties = match_node_properties.findall(':'.join(tmp[1:]))
                        for prop in matched_properties:
                            properties['node'][tmp[0]][prop.split('=')[0]] = prop.split('=')[1]
        else:
            module.fail_json(msg='Failed to load properties from cluster. Is cluster running?')

        result['detected_properties'] = properties

        if state == 'present':
            cmd_set = ''
            result['changed'] = True
            # property not found or having a different value
            if node is None and (name not in properties['cluster'] or properties['cluster'][name] != value):
                cmd_set = 'pcs %(cib_file_param)s property set %(name)s=%(value)s' % module.params
            elif node is not None and (node not in properties['node'] or name not in properties['node'][node] or properties['node'][node][name] != value):
                cmd_set = 'pcs %(cib_file_param)s property set --node %(node)s %(name)s=%(value)s' % module.params
            else:
                result['changed'] = False
            if not module.check_mode and result['changed']:
                rc, out, err = module.run_command(cmd_set)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to set property with cmd : '" + cmd_set + "'", output=out, error=err)

        elif state == 'absent':
            result['changed'] = True
            cmd_unset = ''
            # property found but it should not be set
            if node is None and name in properties['cluster']:
                cmd_unset = 'pcs %(cib_file_param)s property unset %(name)s' % module.params
            elif node is not None and node in properties['node'] and name in properties['node'][node]:
                cmd_unset = 'pcs %(cib_file_param)s property unset --node %(node)s %(name)s' % module.params
            else:
                result['changed'] = False
            if not module.check_mode and result['changed']:
                rc, out, err = module.run_command(cmd_unset)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to unset property with cmd: '" + cmd_unset + "'", output=out, error=err)

        # END of module
        module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
