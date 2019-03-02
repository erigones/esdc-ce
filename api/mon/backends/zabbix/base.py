from logging import getLogger, INFO, WARNING, CRITICAL, ERROR
from time import time
from datetime import timedelta
from operator import itemgetter
from datetime import datetime
from subprocess import call

from django.utils.six import iteritems, text_type
from zabbix_api import ZabbixAPI, ZabbixAPIException

from que.tasks import get_task_logger
from api.mon.backends.abstract import VM_KWARGS_KEYS, NODE_KWARGS_KEYS
from api.mon.backends.zabbix.server import ZabbixMonitoringServer
from api.mon.backends.zabbix.utils import parse_zabbix_result
from api.mon.backends.zabbix.exceptions import MonitoringError, InternalMonitoringError, RemoteObjectDoesNotExist

logger = getLogger(__name__)
task_logger = get_task_logger(__name__)

RESULT_CACHE_TIMEOUT = 3600


def cache_result(f):
    """
    Decorator for caching simple function output.
    """

    def wrap(obj, *args, **kwargs):
        if kwargs.pop('bypass_cache', False):
            return f(obj, *args, **kwargs)

        key = f.__name__ + '_' + '_'.join(map(str, args))

        try:
            res, expiry = obj.__cache__[key]
            now = int(time())

            if now > expiry:
                del obj.__cache__[key]
                raise KeyError
        except (KeyError, ValueError, TypeError):
            res = f(obj, *args, **kwargs)

            if res:  # Cache only if valid result is found
                expiry = int(time()) + RESULT_CACHE_TIMEOUT
                obj.__cache__[key] = (res, expiry)

        return res

    return wrap


class ZabbixBase(object):
    """
    Danube Cloud methods for working with Zabbix. #219
    """
    __cache__ = None  # Store output from methods with @cache_result decorator

    NO = 0
    YES = 1
    HOST_MONITORED = 0
    HOST_UNMONITORED = 1
    HOSTINTERFACE_AGENT = 1
    HOSTINTERFACE_AGENT_PORT = 10050
    CUSTOM_ALERT_ITEM = 'alert'
    NOT_CLASSIFIED = 0
    INFORMATION = 1
    WARNING = 2
    AVERAGE = 3
    HIGH = 4
    DISASTER = 5
    PROBLEM_ONE = 1
    PROBLEM_ALL = 2
    NO_PROXY = 0

    _log_prefix = ''
    zapi = None
    server = None
    enabled = False
    connected = False

    # "obj" is a object (node or vm) which will be represented by a zabbix host
    _obj_host_id_attr = 'id'  # object's attribute which will return a string suitable for zabbix host id
    _obj_host_name_attr = 'name'  # object's attribute which will return a string suitable for tech. zabbix host name
    _obj_host_info_attr = 'zabbix_host'  # object's attribute which will return saved host info or empty dict
    _obj_host_save_method = 'save_zabbix_host'  # object's method which will be called with host info dict as argument

    def __init__(self, dc, api_login=True, zapi=None):
        self.__cache__ = {}
        self.settings = dc.settings
        self.zapi = zapi
        self._log_prefix = '[%s:%s] ' % (self.__class__.__name__, dc.name)

        if self.settings.MON_ZABBIX_ENABLED:
            self.enabled = True
            self.sender = self.settings.MON_ZABBIX_SENDER
            self.server = ZabbixMonitoringServer(dc)

            if api_login:
                self.init()

    def __hash__(self):
        if not self.enabled:
            raise RuntimeError('%r is not enabled' % self)
        return hash((self.__class__.__name__, self.server.connection_id))

    @property
    def connection_id(self):
        return self.server.connection_id

    def log(self, level, msg, *args):
        logger.log(level, self._log_prefix + msg, *args)

    def get_log_fun(self, task_log):
        log_prefix = self._log_prefix

        def log_fun(level, msg, *args):
            msg = log_prefix + msg
            logger.log(level, msg, *args)
            task_log.add(level, msg % args)

        return log_fun

    def reset_cache(self):
        """Clear item cache"""
        self.log(INFO, 'Resetting object cache')
        self.__cache__.clear()

    @property
    def login_error(self):
        return None

    @login_error.setter
    def login_error(self, value):
        pass

    def init(self):
        """Initialize zapi and try to login"""
        if not self.enabled:
            raise MonitoringError('Zabbix support is disabled')

        self.reset_cache()

        if self.zapi and self.zapi.logged_in:
            self.log(INFO, 'Reusing zabbix connection to "%s"', self.zapi.server)
            self.login_error = None
            self.connected = True
        else:
            settings = self.settings
            self.log(INFO, 'Establishing zabbix connection to "%s"', settings.MON_ZABBIX_SERVER)
            self.connected = False
            self.zapi = ZabbixAPI(server=settings.MON_ZABBIX_SERVER, user=settings.MON_ZABBIX_HTTP_USERNAME,
                                  passwd=settings.MON_ZABBIX_HTTP_PASSWORD, timeout=settings.MON_ZABBIX_TIMEOUT,
                                  log_level=WARNING, ssl_verify=settings.MON_ZABBIX_SERVER_SSL_VERIFY)

            # Login and save zabbix credentials
            try:
                self.zapi.login(settings.MON_ZABBIX_USERNAME, settings.MON_ZABBIX_PASSWORD, save=True)
            except ZabbixAPIException as e:
                err = 'Zabbix API login error (%s)' % e
                self.log(CRITICAL, err)
                self.login_error = err
            else:
                self.login_error = None
                self.connected = True

        return self.connected

    @classmethod
    def host_id(cls, obj):
        return getattr(obj, cls._obj_host_id_attr)

    @classmethod
    def host_name(cls, obj):
        return getattr(obj, cls._obj_host_name_attr)

    @classmethod
    def host_info(cls, obj):
        return getattr(obj, cls._obj_host_info_attr)

    @classmethod
    def host_save(cls, obj, host):
        return getattr(obj, cls._obj_host_save_method)(host)

    @classmethod
    def get_cached_hostid(cls, obj, default=None):
        try:
            return cls.host_info(obj)['hostid']
        except KeyError:
            return default

    @staticmethod
    def _get_kwargs(obj, wanted):
        """Helper for getting retrieving attributes from object"""
        ret = {}

        for attr in wanted:
            ret[attr] = getattr(obj, attr)

        return ret

    @classmethod
    def _vm_kwargs(cls, vm):
        """Create dict of VM attributes mapping used in string formatting"""
        return cls._get_kwargs(vm, VM_KWARGS_KEYS)

    @classmethod
    def _node_kwargs(cls, node):
        """Create dict of compute node attributes mapping used in string formatting"""
        return cls._get_kwargs(node, NODE_KWARGS_KEYS)

    @staticmethod
    def _id_or_name(value):
        """Helper method for parsing settings"""
        try:
            return int(value)
        except (ValueError, TypeError):
            return value

    @staticmethod
    def _zabbix_result(result, key):
        """Parse zabbix result"""
        return parse_zabbix_result(result, key)

    def _send_data(self, host, key, value):
        """Use zabbix_sender to send a value to zabbix trapper item defined by host & key"""
        return call((self.sender, '-z', self.server.address, '-s', host, '-k', key, '-o', value))

    @cache_result
    def _zabbix_get_templateid(self, name):
        """Query Zabbix API for templateid of the template given as argument"""
        res = self.zapi.template.get({
            'filter': {
                'host': name,
            }
        })

        return self._zabbix_result(res, 'templateid')

    @cache_result
    def _zabbix_get_groupid(self, name):
        """Query Zabbix API for groupid of the host group given as argument"""
        res = self.zapi.hostgroup.get({
            'filter': {
                'name': name,
            }
        })

        return self._zabbix_result(res, 'groupid')

    @cache_result
    def _zabbix_get_proxyid(self, name):
        """Query Zabbix API for proxyid of the proxy name given as argument"""
        res = self.zapi.proxy.get({
            'filter': {
                'host': name,
            }
        })

        return self._zabbix_result(res, 'proxyid')

    @cache_result
    def _zabbix_get_serviceid(self, name):
        """Query Zabbix API for service id of the service given as argument"""
        res = self.zapi.service.get({
            'filter': {
                'name': name,
            }
        })

        return self._zabbix_result(res, 'serviceid')

    def _zabbix_get_children_serviceids(self, serviceid):
        """Query Zabbix API for children service IDs of the service ID given as argument;
        Used only once in node lifetime => no need for caching"""
        res = self.zapi.service.get({
            'parentids': serviceid,
        })

        try:
            return [i['serviceid'] for i in res]
        except (KeyError, IndexError) as e:
            logger.exception(e)
            raise RemoteObjectDoesNotExist(e)

    @cache_result
    def _zabbix_get_items(self, host, keys, search_params=None):
        """Query Zabbix API for item info of the host and item keys given as arguments"""
        if search_params:
            if 'filter' not in search_params:
                search_params['filter'] = {}

            search_params['filter']['host'] = host
        else:
            search_params = {'filter': {'host': host, 'key_': keys}, 'sortfield': ['itemid'], 'sortorder': 0}

        search_params['output'] = ['itemid', 'name', 'status', 'units', 'description']
        search_params['selectHosts'] = ['hostid', 'host', 'name']

        return self.zapi.item.get(search_params)

    def _zabbix_get_triggerid(self, hostid, desc):
        """Query Zabbix API for triggerid of the host and description given as argument;
        Used only once in node lifetime => no need for caching"""
        res = self.zapi.trigger.get({
            'hostids': hostid,
            'filter': {
                'description': desc,
            }
        })

        return self._zabbix_result(res, 'triggerid')

    def _zabbix_get_sla(self, serviceid, start, end):
        """Query Zabbix API for SLA of service with id serviceid for time interval specified by start and end"""
        res = self.zapi.service.getsla({
            'serviceids': serviceid,
            'intervals': [
                {'from': start, 'to': end},
            ]
        })

        try:
            return res[serviceid]['sla'][0]['sla']
        except (KeyError, IndexError) as e:
            logger.exception(e)
            raise RemoteObjectDoesNotExist(e)

    def _get_proxy_id(self, proxy):
        """Return Zabbix proxy ID"""
        if not proxy:
            return self.NO_PROXY

        proxy = self._id_or_name(proxy)

        if isinstance(proxy, int):
            return proxy

        try:
            return int(self._zabbix_get_proxyid(proxy))
        except MonitoringError as ex:
            logger.exception(ex)
            raise RemoteObjectDoesNotExist('Cannot find zabbix proxy id for proxy "%s"' % proxy)

    def _get_or_create_hostgroups(self, obj_kwargs, hostgroup, dc_name, hostgroups=(), log=None):
        """Return set of zabbix hostgroup IDs for an object"""
        from api.mon.backends.zabbix.containers.host_group import ZabbixHostGroupContainer

        log = log or self.log
        gids = set()
        hostgroup = self._id_or_name(hostgroup)

        if isinstance(hostgroup, int):
            gids.add(hostgroup)
        else:
            try:
                gids.add(int(self._zabbix_get_groupid(hostgroup)))
            except MonitoringError as ex:
                log(CRITICAL, 'Could not fetch zabbix hostgroup id for main hostgroup "%s"', hostgroup)
                raise ex  # The main hostgroup must exist!

        for name in hostgroups:
            name = self._id_or_name(name)

            # If we already know the id of the hostgroup, we use it.
            if isinstance(name, int):
                gids.add(name)
                continue

            # Otherwise, local hostgroup has to be checked first.
            hostgroup_name = name.format(**obj_kwargs)
            qualified_hostgroup_name = ZabbixHostGroupContainer.hostgroup_name_factory(dc_name, hostgroup_name)

            try:
                gids.add(int(self._zabbix_get_groupid(qualified_hostgroup_name)))
            except RemoteObjectDoesNotExist:
                pass
            else:
                continue

            # If the ~local~ hostgroup (with dc_name prefix) doesn't exist,
            # we look for a ~global~ hostgroup (without dc_name prefix).
            try:
                gids.add(int(self._zabbix_get_groupid(hostgroup_name)))
            except RemoteObjectDoesNotExist:
                log(WARNING, 'Could not fetch zabbix hostgroup id for the hostgroup "%s". '
                             'Creating a new hostgroup instead.', hostgroup_name)
            else:
                continue

            # If not even the ~global~ hostgroup exists, we are free to create a ~local~ hostgroup.
            new_hostgroup = ZabbixHostGroupContainer.create_from_name(self.zapi, qualified_hostgroup_name)
            gids.add(new_hostgroup.zabbix_id)
            log(INFO, 'Monitoring hostgroup "%s" was successfully created', hostgroup_name)

        return gids

    def _get_templates(self, obj_kwargs, templates, log=None):
        """Return set of zabbix template IDs for an object"""
        log = log or self.log
        tids = set()

        for name in templates:
            name = self._id_or_name(name)

            if isinstance(name, int):
                tids.add(name)
            else:
                try:
                    tids.add(int(self._zabbix_get_templateid(name.format(**obj_kwargs))))
                except MonitoringError:
                    log(ERROR, 'Could not fetch zabbix template id for template "%s"', name)
                    continue

        return tids

    def _get_templates_by_tags(self, tags):
        """Return set of zabbix template IDs according to a list of tags mapped to template names"""
        tids = set()

        for tag in tags:
            for template in self.zapi.template.get({'search': {'name': tag}, 'output': ['templateid']}):
                tids.add(int(template['templateid']))

        return tids

    def _get_vm_nic_templates(self, vm, vm_kwargs, templates, log=None):
        """Return set of zabbix template IDs for VM's NICs from json_active"""
        log = log or self.log
        tids = set()

        for real_nic_id, array_nic_id in vm.json_active_get_nics_map().items():
            nic = {'net': real_nic_id, 'nic_id': array_nic_id}
            nic.update(vm_kwargs)

            for template in templates:
                if isinstance(template, (tuple, list)):
                    try:
                        name = template[real_nic_id]
                    except IndexError:
                        log(WARNING, 'Missing template for real_nic_id %d in TEMPLATES_NIC setting %s',
                            real_nic_id, template)
                        continue
                else:
                    name = template

                name = self._id_or_name(name)

                if isinstance(name, int):
                    tids.add(name)
                else:
                    try:
                        tids.add(int(self._zabbix_get_templateid(str(name).format(**nic))))
                    except MonitoringError:
                        log(ERROR, 'Could not fetch zabbix template id for nic template "%s"', name)
                        continue

        return tids

    def _get_vm_disk_templates(self, vm, vm_kwargs, templates, log=None):
        """Return set of zabbix template IDs for VM's disk from json_active"""
        log = log or self.log
        tids = set()

        for real_disk_id, array_disk_id in vm.json_active_get_disks_map().items():
            disk = {'disk': real_disk_id, 'disk_id': array_disk_id}
            disk.update(vm_kwargs)

            for template in templates:
                if isinstance(template, (tuple, list)):
                    try:
                        name = template[array_disk_id]
                    except IndexError:
                        log(WARNING, 'Missing template for real_disk_id %d in TEMPLATES_DISK setting %s',
                            real_disk_id, template)
                        continue
                else:
                    name = template

                name = self._id_or_name(name)

                if isinstance(name, int):
                    tids.add(name)
                else:
                    try:
                        tids.add(int(self._zabbix_get_templateid(str(name).format(**disk))))
                    except MonitoringError:
                        log(ERROR, 'Could not fetch zabbix template id for disk template "%s"', name)
                        continue

        return tids

    def _get_host_interface(self, dns, ip, port=HOSTINTERFACE_AGENT_PORT, useip=True):
        """Return dict with host interface information for DNS hostname and IP address"""
        if not ip and useip and dns:
            useip = False

        return {
            'dns': dns,
            'ip': ip,
            'main': self.YES,
            'useip': int(useip),
            'type': self.HOSTINTERFACE_AGENT,
            'port': str(port),
        }

    def get_host(self, zabbix_id, log=None):
        """Return zabbix host according to vm_uuid or node_uuid (zabbix_id)"""
        log = log or self.log

        try:
            res = self.zapi.host.get({
                'filter': {'host': zabbix_id},
                'output': 'extend',
                'selectInterfaces': 'extend',
                'selectMacros': 'extend',
                'selectGroups': 'extend',
                'selectParentTemplates': ['templateid', 'hostid'],
            })
        except ZabbixAPIException as e:
            log(ERROR, 'Zabbix API Error in get_host(%s): %s', zabbix_id, e)
            raise e

        try:
            return parse_zabbix_result(res)
        except RemoteObjectDoesNotExist:
            return {}

    def has_host_info(self, obj):
        """Return True if host info is saved in obj"""
        return 'hostid' in self.host_info(obj)

    def save_host_info(self, obj, host=None, log=None):
        """Save zabbix host dict into obj.zabbix_info (vm.info['zabbix'] or node.json['zabbix'])"""
        log = log or self.log

        if host is None:
            host = self.get_host(self.host_id(obj), log=log)

        # noinspection PyProtectedMember
        log(INFO, 'Saving zabbix host info into %s %s', obj._meta.verbose_name_raw, obj)
        self.host_save(obj, host)

    def get_hostid(self, obj, log=None):
        """Return zabbix hostid from obj.zabbix_info (vm.info['zabbix'] or node.json['zabbix'])"""
        try:
            return self.host_info(obj)['hostid']
        except KeyError:
            host = self.get_host(self.host_id(obj), log=log)

            if 'hostid' in host:
                self.save_host_info(obj, host=host, log=log)
                return host['hostid']
            else:
                return None

    def update_host(self, hostid, log=None, **params):
        """Update parameters of one Zabbix host identified by hostid. Return hostid of updated host or False/None"""
        log = log or self.log
        params['hostid'] = hostid

        try:
            res = self.zapi.host.update(params)
        except ZabbixAPIException as e:
            log(ERROR, 'Zabbix API Error in update_host(%s): %s', hostid, e)
            return False

        return parse_zabbix_result(res, 'hostids', from_get_request=False)

    @staticmethod
    def _gen_host_groups(groups):
        """Return array of hostgroups suitable for host create/update api call"""
        return [{'groupid': str(i)} for i in groups]

    @staticmethod
    def _parse_host_groups(host):
        """Return set of group IDs from zabbix host dict"""
        return set([int(i['groupid']) for i in host.get('groups', ())])

    @staticmethod
    def _gen_host_templates(templates):
        """Return array of templates suitable for host create/update api call"""
        return [{'templateid': str(i)} for i in templates]

    @staticmethod
    def _parse_host_templates(host):
        """Return set of template IDs from zabbix host dict"""
        return set([int(i['templateid']) for i in host.get('parentTemplates', ())])

    @staticmethod
    def _gen_host_macros(macros):
        """Return array of macros suitable for host create/update api call"""
        return [{'macro': k, 'value': v} for k, v in iteritems(macros)]

    @staticmethod
    def _parse_host_macros(host):
        """Return dict of macro name : value from zabbix host dict"""
        macros = host.get('macros', ())
        if isinstance(macros, dict):
            macros = macros.values()
        # noinspection PyTypeChecker
        return {str(i['macro']): str(i['value']) for i in macros}

    @staticmethod
    def _parse_host_interfaces(host):
        """Return list of host interfaces"""
        interfaces = host.get('interfaces', ())  # Zabbix 2.2 changed interfaces to list
        if isinstance(interfaces, dict):  # In zabbix <= 2.0 the interfaces was a object/dict
            interfaces = interfaces.values()
        return interfaces

    def _create_host(self, obj, interface, groups=(), templates=(), macros=None, status=HOST_MONITORED,
                     proxy_id=NO_PROXY, log=None):
        """Create new Zabbix host from model object. Return hostid of the created host or False if an error occurred"""
        log = log or self.log
        params = {
            'host': self.host_id(obj),
            'name': self.host_name(obj),
            'status': status,
            'interfaces': [interface],
            'groups': self._gen_host_groups(groups),
            'templates': self._gen_host_templates(templates),
            'proxy_hostid': proxy_id,
        }

        if macros is not None:
            params['macros'] = self._gen_host_macros(macros)

        try:
            res = self.zapi.host.create(params)
        except ZabbixAPIException as e:
            # noinspection PyProtectedMember
            log(ERROR, 'Zabbix API Error in create_host(%s %s): %s', obj._meta.verbose_name_raw, obj, e)
            return False

        return parse_zabbix_result(res, 'hostids', from_get_request=False)

    def delete_host(self, hostid, log=None):
        """Delete host from Zabbix"""
        log = log or self.log

        try:
            res = self.zapi.host.delete([hostid])
        except ZabbixAPIException as e:
            log(ERROR, 'Zabbix API Error in delete_host(%s): %s', hostid, e)
            return False

        return parse_zabbix_result(res, 'hostids', from_get_request=False)

    @classmethod
    def _diff_interfaces(cls, obj, host, interface):
        params = {}

        # There should be one zabbix agent interface
        hi = None
        try:
            interfaces = cls._parse_host_interfaces(host)

            for i, iface in enumerate(interfaces):
                if int(iface['type']) == cls.HOSTINTERFACE_AGENT and int(iface['main']) == cls.YES:
                    if hi:
                        # noinspection PyProtectedMember
                        raise ZabbixAPIException('Zabbix host ID "%s" for %s %s has multiple Zabbix Agent '
                                                 'configurations' % (host['hostid'], obj._meta.verbose_name_raw, obj))

                    # Zabbix host interface found, let's check it out
                    hi = iface

                    if (iface['dns'] != interface['dns']
                            or iface['ip'] != interface['ip']
                            or str(iface['port']) != str(interface['port'])
                            or str(iface['useip']) != str(interface['useip'])):
                        # Host ip or dns changed -> update host interface
                        interface['interfaceid'] = iface['interfaceid']
                        interfaces[i] = interface
                        params['interfaces'] = interfaces

        except (IndexError, KeyError):
            pass

        if not hi:
            # noinspection PyProtectedMember
            raise ZabbixAPIException('Zabbix host ID "%s" for %s %s is missing a valid main '
                                     'Zabbix Agent configuration' % (host['hostid'], obj._meta.verbose_name_raw, obj))
        return params

    @classmethod
    def _diff_basic_info(cls, obj, host, proxy_id, status):
        params = {}

        # Check zabbix host ID (name)
        host_id = cls.host_id(obj)

        if host['host'] != host_id:
            params['host'] = host_id

        # Check zabbix visible name
        host_name = cls.host_name(obj)

        if host['name'] != host_name:
            # Hostname changed! -> update name
            params['name'] = host_name

        # Check zabbix proxy ID
        proxy_hostid = int(host.get('proxy_hostid', cls.NO_PROXY))

        if proxy_hostid != proxy_id:
            params['proxy_hostid'] = proxy_id

        # Always set to monitored (because this tasks is also run after deploying VM, which had monitoring disabled)
        if int(host['status']) != status:
            # Status changed! -> update status
            params['status'] = status

        return params

    @classmethod
    def _diff_templates(cls, host, templates):
        params = {}
        # Always replace current zabbix templates with configured templates
        zx_templates = cls._parse_host_templates(host)
        new_templates = set(templates)

        if zx_templates != new_templates:
            # Templates configuration changed!
            params['templates'] = cls._gen_host_templates(new_templates)
            # Removed templates need to be cleared properly
            removed_templates = zx_templates - new_templates

            if removed_templates:
                params['templates_clear'] = cls._gen_host_templates(removed_templates)

        return params

    @classmethod
    def _diff_host_groups(cls, host, groups):
        params = {}
        # Always replace current zabbix groups with configured groups
        zx_groups = cls._parse_host_groups(host)
        new_groups = set(groups)

        if zx_groups != new_groups:
            # Groups configuration changed!
            params['groups'] = cls._gen_host_groups(new_groups)

        return params

    @classmethod
    def _diff_macros(cls, host, macros):
        params = {}
        # Replace macros only if specified
        if macros is not None:
            zx_macros = cls._parse_host_macros(host)

            if zx_macros != macros:
                # Host macros changed!
                params['macros'] = cls._gen_host_macros(macros)

        return params

    def _diff_host(self, obj, host, interface, groups=(), templates=(), macros=None, status=HOST_MONITORED,
                   proxy_id=NO_PROXY):
        """Compare DB object and host (Zabbix) configuration and create an update dict; Issue #chili-331"""

        # Empty params means no update is needed
        params = {}

        params.update(self._diff_interfaces(obj, host, interface))
        params.update(self._diff_basic_info(obj, host, proxy_id, status))
        params.update(self._diff_templates(host, templates))
        params.update(self._diff_host_groups(host, groups))
        params.update(self._diff_macros(host, macros))

        return params

    def _create_service(self, name, parentid, algorithm=PROBLEM_ONE, sla=99.0, sortorder=0, triggerid=None):
        """Create Zabbix IT Service"""
        params = {
            'name': name,
            'parentid': parentid,
            'algorithm': algorithm,
            'sortorder': sortorder,
        }

        if sla:
            params['showsla'] = self.YES
            params['goodsla'] = sla
        else:
            params['showsla'] = self.NO

        if triggerid:
            params['triggerid'] = triggerid

        try:
            res = self.zapi.service.create(params)
        except ZabbixAPIException as e:
            logger.exception(e)
            raise InternalMonitoringError(text_type(e))

        return parse_zabbix_result(res, 'serviceids', from_get_request=False)

    def _update_service(self, serviceid, **params):
        """Update Zabbix IT Service"""
        params['serviceid'] = serviceid

        try:
            res = self.zapi.service.update(params)
        except ZabbixAPIException as e:
            logger.exception(e)
            raise InternalMonitoringError(text_type(e))

        return parse_zabbix_result(res, 'serviceids', from_get_request=False)

    def get_history(self, hosts, items, history, since, until, items_search=None, skip_nonexistent_items=False):
        """Return monitoring history for selected zabbix host, items and period"""
        res = {'history': [], 'items': []}

        now = int(datetime.now().strftime('%s'))
        max_period = self.settings.MON_ZABBIX_GRAPH_MAX_PERIOD
        max_history = now - self.settings.MON_ZABBIX_GRAPH_MAX_HISTORY
        period = until - since
        since_history = None
        until_history = None
        since_trend = None
        until_trend = None
        itemids = set()

        if until < max_history or period > max_period:  # trends only
            until_trend = until
            since_trend = since
        else:  # history only
            until_history = until
            since_history = since

        try:
            for host in hosts:
                host_items = self._zabbix_get_items(host, items, search_params=items_search)

                if not host_items:
                    if skip_nonexistent_items:
                        continue
                    else:
                        raise ZabbixAPIException('Cannot find items for host "%s" in Zabbix' % host)

                itemids.update(i['itemid'] for i in host_items)
                res['items'].extend(host_items)

            # noinspection PyTypeChecker
            params = {
                'itemids': list(itemids),
                'history': history,
                'sortfield': 'clock',
                'sortorder': 'ASC',
                'output': 'extend',
            }

            if since_trend and until_trend:
                params['time_from'] = since_trend
                params['time_till'] = until_trend
                # Zabbix trend.get does not support sorting -> https://support.zabbix.com/browse/ZBXNEXT-3974
                res['history'] = sorted(self.zapi.trend.get(params), key=itemgetter('clock'))

            if since_history and until_history:
                params['time_from'] = since_history
                params['time_till'] = until_history
                res['history'] += self.zapi.history.get(params)

        except ZabbixAPIException as exc:
            self.log(ERROR, 'Zabbix API Error in get_history(%s, %s): %s', hosts, items, exc)
            raise InternalMonitoringError('Zabbix API Error while retrieving history (%s)' % exc)

        else:
            return res

    @staticmethod
    def event_status(value):
        value = int(value)

        if value == 0:
            return 'OK'
        elif value == 1:
            return 'PROBLEM'
        else:
            return 'UNKNOWN'

    def _get_alert_events(self, triggers, since=None, until=None, max_days=7):
        """Get all events related to triggers"""
        triggerids = [t['triggerid'] for t in triggers]
        events = {}
        params = {
            'triggerids': triggerids,
            'object': 0,  # 0 - trigger
            'source': 0,  # 0 - event created by a trigger
            'output': 'extend',
            'select_acknowledges': 'extend',
            'sortfield': ['clock', 'eventid'],
            'sortorder': 'DESC',
            'nodeids': 0,
        }

        if since and until:
            params['time_from'] = since
            params['time_till'] = until
        else:
            since = datetime.now() - timedelta(days=max_days)
            params['time_from'] = since.strftime('%s')

        for e in self.zapi.event.get(params):
            events.setdefault(e['objectid'], []).append(e)

        # Because of time limits, there may be some missing events for some trigger IDs
        missing_eventids = [t['lastEvent']['eventid'] for t in triggers if
                            t['lastEvent'] and t['triggerid'] not in events]

        if missing_eventids:
            for e in self.zapi.event.get({'eventids': missing_eventids, 'source': 0, 'output': 'extend',
                                          'select_acknowledges': 'extend', 'nodeids': 0}):
                events.setdefault(e['objectid'], []).append(e)

        return events

    def _get_alerts(self, groupids=None, hostids=None, monitored=True, maintenance=False, skip_dependent=True,
                    expand_description=False, select_hosts=('hostid',), active_only=True, priority=None,
                    output=('triggerid', 'state', 'error', 'description', 'priority', 'lastchange'), **kwargs):
        """Return iterator of current zabbix triggers"""
        params = {
            'groupids': groupids,
            'hostids': hostids,
            'monitored': monitored,
            'maintenance': maintenance,
            'skipDependent': skip_dependent,
            'expandDescription': expand_description,
            'filter': {'priority': priority},
            'selectHosts': select_hosts,
            'selectLastEvent': 'extend',  # API_OUTPUT_EXTEND
            'output': output,
            'sortfield': 'lastchange',
            'sortorder': 'DESC',  # ZBX_SORT_DOWN
        }

        if active_only:  # Whether to show current active alerts only
            params['filter']['value'] = 1  # TRIGGER_VALUE_TRUE

        params.update(kwargs)

        # If trigger is lost (broken expression) we skip it
        return (trigger for trigger in self.zapi.trigger.get(params) if trigger['hosts'])

    @classmethod
    def _collect_trigger_events(cls, related_events):
        for event in related_events:
            yield {
                'eventid': int(event['eventid']),
                'clock': int(event['clock']),
                'value': int(event['value']),
                'status': cls.event_status(event['value']),
                'acknowledged': bool(int(event['acknowledged'])),
                'acknowledges': [{
                    'acknowledgeid': int(ack['acknowledgeid']),
                    'clock': int(ack['clock']),
                    'message': ack['message'],
                    'user': ack['alias'],
                } for ack in event['acknowledges']]
            }

    # noinspection PyUnusedLocal
    def show_alerts(self, hostids=None, since=None, until=None, last=None, show_events=True):
        """Show current or historical events (alerts)"""
        t_output = ('triggerid', 'state', 'error', 'url', 'expression', 'description', 'priority', 'type', 'comments',
                    'lastchange')
        t_hosts = ('hostid', 'name', 'maintenance_status', 'maintenance_type', 'maintenanceid')
        t_options = {'expand_description': True, 'output': t_output, 'select_hosts': t_hosts}

        if hostids is not None:
            t_options['hostids'] = hostids

        if since and until:
            t_options['lastChangeSince'] = since
            t_options['lastChangeTill'] = until
            t_options['active_only'] = False

        if last is not None:
            t_options['limit'] = last
            t_options['active_only'] = False

        # Fetch triggers
        triggers = list(self._get_alerts(**t_options))

        # Get notes (dict) = related events + acknowledges
        if show_events:
            events = self._get_alert_events(triggers, since=since, until=until)
        else:
            events = {}

        for trigger in triggers:
            host = trigger['hosts'][0]
            hostname = host['name']
            related_events = events.get(trigger['triggerid'], ())
            trigger_events = self._collect_trigger_events(related_events)
            last_event = trigger['lastEvent']

            if last_event:
                eventid = int(last_event['eventid'])
                ack = bool(int(last_event['acknowledged']))
            else:
                # WTF?
                eventid = '????'
                ack = None

            yield {
                'eventid': eventid,
                'priority': int(trigger['priority']),
                'hostname': hostname,
                'desc': text_type(trigger['description']),
                'acknowledged': ack,
                'last_change': int(trigger['lastchange']),
                'events': list(trigger_events),
                'error': trigger['error'],
                'comments': trigger['comments'],
                'url': trigger['url'],
            }
