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
module: pcs_resource_defaults
short_description: "wrapper module for 'pcs resource defaults' and 'pcs resource op defaults'"
description:
  - "module for setting and unsetting clusters resource deafults and resource operation defaults using 'pcs' utility"
version_added: "2.4"
options:
  state:
    description:
      - "'present' - ensure that resource default exists with given value"
      - "'absent' - ensure resource default doesn't exist (is unset)"
    required: false
    default: present
    choices: ['present', 'absent']
  defaults_type:
    description:
      - "'meta' - resource meta defaults, 'pcs resource defaults ...'"
      - "'op' - resource operation defaults, 'pcs resource op defaults ...'"
    required: false
    default: meta
    choices: ['meta', 'op']
  name:
    description:
      - name of cluster resource default
    required: true
  value:
    description:
      - value of cluster resource default
    required: false
  cib_file:
    description:
      - "Apply changes to specified file containing cluster CIB instead of running cluster."
    required: false
notes:
   - tested on CentOS 7.4
'''

EXAMPLES = '''
- name: set resource-stickiness=100 to be default for resources
  pcs_resource_defaults:
    name: 'resource-stickiness'
    value: '100'

- name: remove the 'resource-stickiness' resource default
  pcs_resource_defaults:
    name: 'resource-stickiness'
    state: 'absent'

- name: set default operation timeout for resources to 60
  pcs_resource_defaults:
    defaults_type: 'op'
    name: 'timeout'
    value: '60'

- name: remove the custom default operation timeout
  pcs_resource_defaults:
    defaults_type: 'op'
    name: 'timeout'
    state: 'absent'
'''

import os.path
from distutils.spawn import find_executable
from ansible.module_utils.basic import AnsibleModule


def run_module():
        module = AnsibleModule(
            argument_spec=dict(
                state=dict(default="present", choices=['present', 'absent']),
                defaults_type=dict(required=False, default="meta", choices=['meta', 'op']),
                name=dict(required=True),
                value=dict(required=False),
                cib_file=dict(required=False),
            ),
            supports_check_mode=True
        )

        state = module.params['state']
        name = module.params['name']
        defaults_type = module.params['defaults_type']
        value = module.params['value']
        cib_file = module.params['cib_file']

        result = {}

        if find_executable('pcs') is None:
            module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")

        if state == 'present' and value is None:
            module.fail_json(msg="To set a defaults 'value' must be specified.")

        module.params['cib_file_param'] = ''
        if cib_file is not None and os.path.isfile(cib_file):
            module.params['cib_file_param'] = '-f ' + cib_file

        # get defaults list from running cluster
        if defaults_type == 'meta':
            rc, out, err = module.run_command('pcs %(cib_file_param)s resource defaults' % module.params)
        elif defaults_type == 'op':
            rc, out, err = module.run_command('pcs %(cib_file_param)s resource op defaults' % module.params)
        else:
            module.fail_json(msg="'" + defaults_type + "' is not implemented by this module")

        defaults = {}
        if rc == 0:
            for row in out.split('\n')[:-1]:
                if row == 'No defaults set':
                    break
                tmp = row.split(':')
                defaults[tmp[0]] = tmp[1].lstrip()
        else:
            module.fail_json(msg='Failed to load resource defaults from cluster. Is cluster running?')

        result['detected_defaults'] = defaults

        if state == 'present' and (name not in defaults or defaults[name] != value):
            # default not found or having a different value
            result['changed'] = True
            if not module.check_mode:
                if defaults_type == 'meta':
                    cmd_set = 'pcs %(cib_file_param)s resource defaults %(name)s=%(value)s' % module.params
                elif defaults_type == 'op':
                    cmd_set = 'pcs %(cib_file_param)s resource op defaults %(name)s=%(value)s' % module.params
                else:
                    module.fail_json(msg="'" + defaults_type + "' is not implemented by this module")
                rc, out, err = module.run_command(cmd_set)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to set " + defaults_type + " with cmd : '" + cmd_set + "'", output=out, error=err)

        elif state == 'absent' and name in defaults:
            # default found but it should not be set
            result['changed'] = True
            if not module.check_mode:
                if defaults_type == 'meta':
                    cmd_unset = 'pcs %(cib_file_param)s resource defaults %(name)s=' % module.params
                elif defaults_type == 'op':
                    cmd_unset = 'pcs %(cib_file_param)s resource op defaults %(name)s=' % module.params
                else:
                    module.fail_json(msg="'" + defaults_type + "' is not implemented by this module")
                rc, out, err = module.run_command(cmd_unset)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to unset " + defaults_type + " default with cmd: '" + cmd_unset + "'", output=out, error=err)
        else:
            # No change needed
            result['changed'] = False

        # END of module
        module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
