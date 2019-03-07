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
module: pcs_constraint_location
short_description: "wrapper module for 'pcs constraint location'"
description:
  - "module for creating and deleting clusters location constraints using 'pcs' utility"
version_added: "2.4"
options:
  state:
    description:
      - "'present' - ensure that cluster constraint exists"
      - "'absent' - ensure cluster constraints doesn't exist"
    required: false
    default: present
    choices: ['present', 'absent']
  resource:
    description:
      - resource for constraint
    required: true
  node_name:
    description:
      - node name for constraints
    required: true
  score:
    description:
      - constraint score in range -INFINITY..0..INFINITY
    required: false
    default: 'INFINITY'
  cib_file:
    description:
      - "Apply changes to specified file containing cluster CIB instead of running cluster."
      - "This module requires the file to already contain cluster configuration."
    required: false
notes:
   - tested on CentOS 7.3
'''

EXAMPLES = '''
- name: resource resA prefers to run on node1
  pcs_constraint_location:
    resource: 'resA'
    node_name: 'node1'

- name: resource resB avoids running on node2
  pcs_constraint_location:
    resource: 'resB'
    node_name: 'node2'
    score: '-INFINITY'
'''

import os.path
import xml.etree.ElementTree as ET
from distutils.spawn import find_executable

from ansible.module_utils.basic import AnsibleModule


def run_module():
        module = AnsibleModule(
            argument_spec=dict(
                state=dict(default="present", choices=['present', 'absent']),
                resource=dict(required=True),
                node_name=dict(required=True),
                score=dict(required=False, default="INFINITY"),
                cib_file=dict(required=False),
            ),
            supports_check_mode=True
        )

        state = module.params['state']
        resource = module.params['resource']
        node_name = module.params['node_name']
        score = module.params['score']
        cib_file = module.params['cib_file']

        result = {}

        if find_executable('pcs') is None:
            module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")

        module.params['cib_file_param'] = ''
        if cib_file is not None:
            # use cib_file if specified
            if os.path.isfile(cib_file):
                try:
                    current_cib = ET.parse(cib_file)
                except Exception as e:
                    module.fail_json(msg="Error encountered parsing the cib_file - %s" % (e))
                current_cib_root = current_cib.getroot()
                module.params['cib_file_param'] = '-f ' + cib_file
            else:
                module.fail_json(msg="%(cib_file)s is not a file or doesn't exists" % module.params)
        else:
            # get running cluster configuration
            rc, out, err = module.run_command('pcs cluster cib')
            if rc == 0:
                current_cib_root = ET.fromstring(out)
            else:
                module.fail_json(msg='Failed to load cluster configuration', out=out, error=err)

        # try to find the constraint we have defined
        constraint = None
        constraints = current_cib_root.findall("./configuration/constraints/rsc_location")
        for constr in constraints:
            # constraint is considered found if we see resource and node as got through attributes
            if constr.attrib.get('rsc') == resource and constr.attrib.get('node') == node_name:
                constraint = constr
                break

        # location constraint creation command
        cmd_create = 'pcs %(cib_file_param)s constraint location %(resource)s prefers %(node_name)s=%(score)s' % module.params

        # location constriaint deleter command
        if constraint is not None:
            cmd_delete = 'pcs %(cib_file_param)s constraint delete ' % module.params + constraint.attrib.get('id')

        if state == 'present' and constraint is None:
            # constraint should be present, but we don't see it in configuration - lets create it
            result['changed'] = True
            if not module.check_mode:
                rc, out, err = module.run_command(cmd_create)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to create constraint with cmd: '" + cmd_create + "'", output=out, error=err)

        elif state == 'present' and constraint is not None:
            # constraint should be present and we see similar constraint so lets check if it is same
            if score != constraint.attrib.get('score'):
                result['changed'] = True
                if not module.check_mode:
                    rc, out, err = module.run_command(cmd_delete)
                    if rc != 0:
                        module.fail_json(msg="Failed to delete constraint for replacement with cmd: '" + cmd_delete + "'", output=out, error=err)
                    else:
                        rc, out, err = module.run_command(cmd_create)
                        if rc == 0:
                            module.exit_json(**result)
                        else:
                            module.fail_json(msg="Failed to create constraint replacement with cmd: '" + cmd_create + "'", output=out, error=err)

        elif state == 'absent' and constraint is not None:
            # constraint should not be present but we have found something - lets remove that
            result['changed'] = True
            if not module.check_mode:
                rc, out, err = module.run_command(cmd_delete)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to delete constraint with cmd: '" + cmd_delete + "'", output=out, error=err)
        else:
            # constraint should not be present and is not there, nothing to do
            result['changed'] = False

        # END of module
        module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
