#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# (c) 2012-2014, Erigones, s. r. o
# noinspection PyPep8Naming
import xml.etree.ElementTree as ET
import os
import json

try:
    from zabbix_api import ZabbixAPI
except ImportError:
    ZabbixAPI = None

from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = '''
---
module: zabbix_template
short_description: Import templates to Zabbix
description:
    - Import Zabbix templates via Zabbix API
version_added: "1.8"
author: Adam Števko
requirements:
    - zabbix-api python module
options:
    server_url:
        description:
            - Url of Zabbix server, with protocol (http or https).
              C(url) is an alias for C(server_url).
        required: true
        default: null
        aliases: [ "url" ]
    login_user:
        description:
            - Zabbix user name.
        required: true
        default: null
    login_password:
        description:
            - Zabbix user password.
        required: true
        default: null
    state:
        description:
            - Import or delete Zabbix template.
        required: false
        default: "present"
        choices: [ "present", "absent", "import", "export" ]
    template:
        description:
            - Location of template file.
        required: true
    timeout:
        description:
            - The timeout of API request(seconds).
        default: 10
    validate_certs:
        description:
            - Whether to perform HTTPS certificate verification.
        default: False
    format:
        description:
            - Output format of exported template
        default: xml
        choices: [ "xml", "json" ]
notes:
    - Too many concurrent updates to the same group may cause Zabbix to return errors, see examples for a workaround if
    needed.
'''

EXAMPLES = '''
# Base create host groups example
- name: Create host groups
  local_action:
    module: zabbix_group
    server_url: http://monitor.example.com
    login_user: username
    login_password: password
    state: present
    host_groups:
      - Example group1
      - Example group2

# Limit the Zabbix group creations to one host since Zabbix can return an error when doing concurent updates
- name: Create host groups
  local_action:
    module: zabbix_group
    server_url: http://monitor.example.com
    login_user: username
    login_password: password
    state: present
    host_groups:
      - Example group1
      - Example group2
  when: inventory_hostname==groups['group_name'][0]
'''


def indent(elem, level=0):
    """
    As ElementTree doesn't come with prettyprint function and minidom's
    parseString produces ugly XML output, we include our function.
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def get_template_name(module, filename):
    try:
        with open(filename, 'r') as f:
            data = f.read()

        data = json.loads(data)
    except Exception as e:
        module.fail_json(msg="Invalid JSON: %s" % e)
        raise AssertionError

    return data['zabbix_export']['templates'][0]['name']


def get_template_id(module, zbx, name):
    try:
        result = zbx.template.get({
            "output": ["templateid"],
            "filter": {
                "host": [name]
            }
        })
    except Exception as e:
        module.fail_json(msg="Zabbix API problem: %s" % e)
        raise AssertionError

    try:
        return result[0]['templateid']
    except (IndexError, KeyError):
        raise ValueError("Template \"%s\" not found" % name)


def check_template(module, zbx, name):
    try:
        return bool(get_template_id(module, zbx, name))
    except ValueError:
        return False
    except Exception as e:
        module.fail_json(msg="Zabbix API problem: %s" % e)


def import_template(module, zbx, filename, fmt):
    if not os.path.exists(filename):
        module.fail_json(msg="template file %s not found" % filename)

    with open(filename) as f:
        data = f.read()

    try:
        return zbx.configuration.import_({
            "format": fmt,
            "source": data,
            "rules": {
                "items": {
                    "createMissing": True
                },
                "graphs": {
                    "createMissing": True
                },
                "applications": {
                    "createMissing": True
                },
                "triggers": {
                    "createMissing": True
                },
                "templates": {
                    "createMissing": True
                },
                "templateScreens": {
                    "createMissing": True
                },
                "templateLinkage": {
                    "createMissing": True
                },
                "discoveryRules": {
                    "createMissing": True
                }
            }
        })
    except BaseException as e:
        module.fail_json(msg="Zabbix API problem: %s" % e)
        raise AssertionError


def export_template(module, zbx, template_id, target, fmt):
    try:
        result = zbx.configuration.export({
            "format": fmt,
            "options": {
                "templates": [template_id]
            }
        })
    except BaseException as e:
        module.fail_json(msg="Zabbix API problem: %s" % e)
        raise AssertionError

    if fmt == "xml":
        # Pretty print XML
        xml = ET.fromstring(result)
        indent(xml)
        data = ET.tostring(xml)
    else:
        # Pretty print JSON
        data = json.loads(result)
        data = json.dumps(data, indent=4, separators=(',', ': '))

    try:
        with open(target, 'w') as f:
            f.write(data)
    except BaseException as e:
        module.fail_json(msg="Error writing template file %s: %s" % (target, e))
        raise AssertionError


def remove_template(module, zbx, template_id):
    try:
        return zbx.template.delete([template_id])
    except BaseException as e:
        module.fail_json(msg="Zabbix API problem: %s" % e)
        raise AssertionError


def main():
    module = AnsibleModule(
        argument_spec=dict(
            server_url=dict(required=True, default=None, aliases=['url']),
            login_user=dict(required=True),
            login_password=dict(required=True),
            template=dict(required=True),
            state=dict(default="present"),
            timeout=dict(default=10, type='int'),
            target=dict(required=False),
            format=dict(required=False, default="xml"),
            validate_certs=dict(required=False, default=False, type='bool')
        ),
        supports_check_mode=True
    )

    if not ZabbixAPI:
        module.fail_json(msg="Missing required zabbix-api module (check docs or install with: "
                             "pip install zabbix-api-erigones)")
        raise AssertionError

    server_url = module.params['server_url']
    login_user = module.params['login_user']
    login_password = module.params['login_password']
    template = module.params['template']
    state = module.params['state']
    timeout = module.params['timeout']
    target = module.params['target']
    fmt = module.params['format']
    ssl_verify = module.params['validate_certs']

    # login to zabbix
    try:
        # noinspection PyCallingNonCallable
        zbx = ZabbixAPI(server=server_url, timeout=timeout, ssl_verify=ssl_verify)
        zbx.login(login_user, login_password)
    except Exception as e:
        module.fail_json(msg="Failed to connect to Zabbix server: %s" % e)
        raise AssertionError

    changed = False

    if state in ('present', 'import'):
        if os.path.exists(template):
            template_filename = template
            template_name = get_template_name(module, template_filename)
        else:
            module.fail_json(msg="%s not found" % template)
            raise AssertionError
    elif state == 'absent':
        template_name = template
    elif state == 'export':
        template_name = template

        if target is None:
            module.fail_json(msg="with state=%s target is required" % state)
            raise AssertionError
    else:
        module.fail_json(msg="Invalid state: '%s'" % state)
        raise AssertionError

    if check_template(module, zbx, template_name):
        if module.check_mode:
            changed = True

        if state == 'absent':
            template_id = get_template_id(module, zbx, template_name)
            remove_template(module, zbx, template_id)
            changed = True

        if state == 'export':
            template_id = get_template_id(module, zbx, template_name)
            export_template(module, zbx, template_id, target, fmt)
            changed = True
    else:
        if module.check_mode:
            changed = True

        if state in ('present', 'import'):
            # noinspection PyUnboundLocalVariable
            import_template(module, zbx, template_filename, fmt)
            changed = True

    module.exit_json(changed=changed)


if __name__ == '__main__':
    main()
