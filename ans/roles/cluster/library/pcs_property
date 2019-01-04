#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: pcs_property
short_description: Manages I(pacemaker) cluster properties with pcs tool.
options:
  state:
    required: false
    default: present
    choices: [ "absent", "present" ]
  name:
    required: true
    description: name of the property.
  value:
    required: true
    description: value of the property.
'''

def main():
    module = AnsibleModule(
        argument_spec = dict(
            state     = dict(default='present', choices=['present', 'absent']),
            name      = dict(required=True),
            value     = dict(required=True),
        ),
        supports_check_mode=True,
    )

    # TODO check pcs command is available.
    # TODO check pacemaker/corosync is running.

    # Get current property value.
    cmd = "pcs property list %(name)s | awk '/^ / { print $2}'"  % module.params
    rc, out, err = module.run_command(cmd, use_unsafe_shell=True)
    value = out.strip()

    if module.params['state'] == 'absent':
        print "absent?=?"
        if value != '':
            changed = True
            if not module.check_mode:
                cmd = 'pcs property unset %(name)s' % module.params
                module.run_command(cmd)
        else:
            changed = False
        module.exit_json(changed=changed)
    else:
        print "VALUES: %s - %s" % (value, module.params['value'])
        if value != module.params['value']:
            changed = True
            if not module.check_mode:
                cmd = 'pcs property set %(name)s=%(value)s' % module.params
                module.run_command(cmd)
        else:
            changed = False
        module.exit_json(changed=changed, prev="|%s|" % value,  msg="%(name)s=%(value)s" % module.params)

# import module snippets
from ansible.module_utils.basic import *
main()

