#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# (c) 2012-2017, Erigones, s. r. o
try:
    from zabbix_api import ZabbixAPI, ZabbixAPIException
except ImportError:
    ZabbixAPI = ZabbixAPIException = None

from ansible.module_utils.basic import AnsibleModule


def main():
    # noinspection PyShadowingBuiltins
    module = AnsibleModule(
        argument_spec=dict(
            server_url=dict(required=True, default=None, aliases=['url']),
            login_user=dict(required=True),
            login_password=dict(required=True),
            api_method=dict(required=True),
            api_params_dict=dict(required=False, type='dict', default={}),
            api_params_list=dict(required=False, type='list', default=[]),
            timeout=dict(default=10, type='int'),
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
    api_method = module.params['api_method']
    api_params = module.params['api_params_list'] or module.params['api_params_dict']
    timeout = module.params['timeout']
    ssl_verify = module.params['validate_certs']

    # login to zabbix
    try:
        # noinspection PyCallingNonCallable
        zbx = ZabbixAPI(server=server_url, timeout=timeout, ssl_verify=ssl_verify)
        zbx.login(login_user, login_password)
    except Exception as e:
        module.fail_json(msg="Failed to connect to Zabbix server: %s" % e)
        raise AssertionError

    try:
        result = zbx.call(api_method, api_params)
    except ZabbixAPIException as e:
        module.fail_json(msg="Zabbix API error: %s" % e)
        raise AssertionError
    except Exception as e:
        module.fail_json(msg="Unknown failure: %s" % e)
        raise AssertionError
    else:
        if api_method.endswith(('.get', '.isreadable', '.iswritable')):
            changed = False
        else:
            changed = True

    module.exit_json(changed=changed, result=result)


if __name__ == '__main__':
    main()
