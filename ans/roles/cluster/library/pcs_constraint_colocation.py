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
module: pcs_constraint_colocation
short_description: "wrapper module for 'pcs constraint colocation'"
description:
  - "module for creating and deleting clusters colocation constraints using 'pcs' utility"
version_added: "2.4"
options:
  state:
    description:
      - "'present' - ensure that cluster constraint exists"
      - "'absent' - ensure cluster constraints doesn't exist"
    required: false
    default: present
    choices: ['present', 'absent']
  resource1:
    description:
      - first resource for constraint
    required: true
  resource2:
    description:
      - second resource for constraint
    required: true
  resource1_role:
    description:
      - Role of resource1
    required: false
    choices: ['Master', 'Slave', 'Started']
    default: 'Started'
  resource2_role:
    description:
      - Role of resource2
    required: false
    choices: ['Master', 'Slave', 'Started']
    default: 'Started'
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
   - no extra options allowed for constraints
   - "TODO: validation of resource names, score values"
'''

EXAMPLES = '''
- name: prefer resA and resB to run on same node
  pcs_constraint_colocation:
    resource1: 'resA'
    resource2: 'resB'

- name: prefer resA to run on same node as Master resource of resB-master resource
  pcs_constraint_colocation:
    resource1: 'resA'
    resource2: 'resB-master'
    resource2_role: 'Master'
'''

import os.path
import xml.etree.ElementTree as ET
from distutils.spawn import find_executable

from ansible.module_utils.basic import AnsibleModule


def run_module():
        module = AnsibleModule(
            argument_spec=dict(
                state=dict(default="present", choices=['present', 'absent']),
                resource1=dict(required=True),
                resource2=dict(required=True),
                resource1_role=dict(required=False, choices=['Master', 'Slave', 'Started'], default='Started'),
                resource2_role=dict(required=False, choices=['Master', 'Slave', 'Started'], default='Started'),
                score=dict(required=False, default="INFINITY"),
                cib_file=dict(required=False),
            ),
            supports_check_mode=True
        )

        state = module.params['state']
        resource1 = module.params['resource1']
        resource2 = module.params['resource2']
        resource1_role = module.params['resource1_role']
        resource2_role = module.params['resource2_role']
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
        with_roles = False
        detected_role1, detected_role2 = None, None
        # check if we have requested a non-default roles
        if resource1_role != 'Started' or resource2_role != 'Started':
            with_roles = True
        constraints = current_cib_root.findall("./configuration/constraints/rsc_colocation")
        for constr in constraints:
            # constraint is matched using following criteria:
            # - resource order (resource1 with resource2)
            # - resource roles (resource1_role with resource2_role)
            if (constr.attrib.get('rsc') == resource1
                    and constr.attrib.get('with-rsc') == resource2
                    and constr.attrib.get('rsc-role', 'Started') == resource1_role
                    and constr.attrib.get('with-rsc-role', 'Started') == resource2_role):
                constraint = constr
                break

        # additional variables for verbose output
        if constraint is not None:
            result.update({
                'constraint_was_matched': True,
                'score': constraint.attrib.get('score'),
                'resource1_role': constr.attrib.get('rsc-role'),
                'resource2_role': constr.attrib.get('with-rsc-role'),
            })
        else:
            result.update({'constraint_was_matched': False})

        # colocation constraint creation command
        # TODO: check which old versions requires this, the 0.9.162 seems to handle 'Started' role correctly
        if with_roles is True:
            if resource1_role != 'Started' and resource2_role != 'Started':
                cmd_create = 'pcs %(cib_file_param)s constraint colocation add %(resource1_role)s %(resource1)s with %(resource2_role)s %(resource2)s %(score)s' % module.params
            elif resource1_role != 'Started' and resource2_role == 'Started':
                cmd_create = 'pcs %(cib_file_param)s constraint colocation add %(resource1_role)s %(resource1)s with %(resource2)s %(score)s' % module.params
            elif resource1_role == 'Started' and resource2_role != 'Started':
                cmd_create = 'pcs %(cib_file_param)s constraint colocation add %(resource1)s with %(resource2_role)s %(resource2)s %(score)s' % module.params
        else:
            cmd_create = 'pcs %(cib_file_param)s constraint colocation add %(resource1)s with %(resource2)s %(score)s' % module.params

        # colocation constraint deletion command
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
            # constraint should be present, lets see if it has different score from requested, if yes, then we do update
            if constraint.attrib.get('score', 'INFINITY') != score:
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
