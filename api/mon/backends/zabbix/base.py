from logging import getLogger, INFO, WARNING, CRITICAL, ERROR
from time import time
from operator import itemgetter
from datetime import datetime
from subprocess import call
import re

from django.utils.six import iteritems
from django.db.models import Q
from frozendict import frozendict
from zabbix_api import ZabbixAPI, ZabbixAPIException, ZabbixAPIError

from vms.models import Dc
from api.mon.backends.abstract import VM_KWARGS_KEYS, NODE_KWARGS_KEYS, MonitoringError

logger = getLogger(__name__)

RESULT_CACHE_TIMEOUT = 3600


class ZabbixError(MonitoringError):
    """
    Custom zabbix exception - used only as wrapper.
    """
    pass


class ObjectManipulationError(ZabbixError):
    pass


class RemoteObjectDoesNotExist(ZabbixError):
    pass


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
    enabled = False
    connected = False

    # "obj" is a object (node or vm) which will be represented by a zabbix host
    _obj_host_id_attr = 'id'  # object's attribute which will return a string suitable for zabbix host id
    _obj_host_name_attr = 'name'  # object's attribute which will return a string suitable for tech. zabbix host name
    _obj_host_info_attr = 'zabbix_host'  # object's attribute which will return saved host info or empty dict
    _obj_host_save_method = 'save_zabbix_host'  # object's method which will be called with host info dict as argument

    def __init__(self, settings, api_login=True, zapi=None, name='?'):
        self.__cache__ = {}
        self.settings = settings
        self.zapi = zapi
        self._log_prefix = '[%s:%s] ' % (self.__class__.__name__, name)

        if settings.MON_ZABBIX_ENABLED:
            self.enabled = True
            self.sender = settings.MON_ZABBIX_SENDER
            self.server = settings.MON_ZABBIX_SERVER.split('/')[2]  # https://<server>

            if api_login:
                self.init()

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
            raise ZabbixError('Zabbix support is disabled')

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
        try:
            return result[0][key]
        except (KeyError, IndexError) as e:
            raise ZabbixError(e)

    def _send_data(self, host, key, value):
        """Use zabbix_sender to send a value to zabbix trapper item defined by host & key"""
        return call((self.sender, '-z', self.server, '-s', host, '-k', key, '-o', value))

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
            raise ZabbixError(e)

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
            raise ZabbixError(e)

    def _get_proxy_id(self, proxy):
        """Return Zabbix proxy ID"""
        if not proxy:
            return self.NO_PROXY

        proxy = self._id_or_name(proxy)

        if isinstance(proxy, int):
            return proxy

        try:
            return int(self._zabbix_get_proxyid(proxy))
        except ZabbixError as ex:
            logger.exception(ex)
            raise ZabbixError('Cannot find zabbix proxy id for proxy "%s"' % proxy)

    def _get_or_create_groups(self, obj_kwargs, hostgroup, dc_name, hostgroups=(), log=None):
        """Return set of zabbix hostgroup IDs for an object"""
        log = log or self.log
        gids = set()
        hostgroup = self._id_or_name(hostgroup)

        if isinstance(hostgroup, int):
            gids.add(hostgroup)
        else:
            try:
                gids.add(int(self._zabbix_get_groupid(hostgroup)))
            except ZabbixError as ex:
                log(CRITICAL, 'Could not fetch zabbix hostgroup id for main hostgroup "%s"', hostgroup)
                raise ex  # The main hostgroup must exist!

        for name in hostgroups:
            name = self._id_or_name(name)

            # If we already know the id of the hostgroup, we use it.
            if isinstance(name, int):
                gids.add(name)
                continue

            # Otherwise, local hostgroup has to be checked first.
            qualified_hostgroup_name = ZabbixHostGroupContainer.hostgroup_name_factory(
                hostgroup_name=name.format(**obj_kwargs),
                dc_name=dc_name
            )

            try:
                gids.add(int(self._zabbix_get_groupid(qualified_hostgroup_name)))
            except ZabbixError:
                pass
            else:
                continue

            # If the ~local~ hostgroup (with dc_name prefix) doesn't exist,
            # we look for a ~global~ hostgroup (without dc_name prefix).
            try:
                gids.add(int(self._zabbix_get_groupid(name.format(**obj_kwargs))))
            except ZabbixError:
                log(WARNING, 'Could not fetch zabbix hostgroup id for the hostgroup "%s". '
                             'Creating a new hostgroup %s instead.', name, qualified_hostgroup_name)
            else:
                continue

            #  If not even the ~global~ hostgroup exists, we are free to create a ~local~ hostgroup.
            gids.add(ZabbixHostGroupContainer(qualified_hostgroup_name, zapi=self.zapi).create().zabbix_id)

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
                except ZabbixError:
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
                    except ZabbixError:
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
                    except ZabbixError:
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
            return res[0]
        except IndexError:
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

        try:
            return res['hostids'][0]
        except (KeyError, IndexError) as e:
            logger.exception(e)
            raise ZabbixError(e)

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

        try:
            return res['hostids'][0]
        except (KeyError, IndexError) as e:
            logger.exception(e)
            raise ZabbixError(e)

    def delete_host(self, hostid, log=None):
        """Delete host from Zabbix"""
        log = log or self.log

        try:
            res = self.zapi.host.delete([hostid])
        except ZabbixAPIException as e:
            log(ERROR, 'Zabbix API Error in delete_host(%s): %s', hostid, e)
            return False

        try:
            return res['hostids'][0]
        except (KeyError, IndexError) as e:
            logger.exception(e)
            raise ZabbixError(e)

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
            return res['serviceids'][0]
        except (ZabbixAPIException, KeyError, IndexError) as e:
            logger.exception(e)
            raise ZabbixError(e)

    def _update_service(self, serviceid, **params):
        """Update Zabbix IT Service"""
        params['serviceid'] = serviceid
        try:
            res = self.zapi.service.update(params)
            return res['serviceids'][0]
        except (ZabbixAPIException, KeyError, IndexError) as e:
            logger.exception(e)
            raise ZabbixError(e)

    def get_history(self, hosts, items, history, since, until, items_search=None):
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
            raise ZabbixError('Zabbix API Error while retrieving history (%s)' % exc)

        else:
            return res

    def get_template_list(self):
        """Query Zabbix API for templates"""
        res = self.zapi.template.get({
            'output': ['name', 'host', 'templateid', 'description']
        })

        try:
            return res
        except (KeyError, IndexError) as e:
            logger.exception(e)
            raise ZabbixError(e)

    def get_hostgroup_list(self):
        """Query Zabbix API for hostgroups"""
        res = self.zapi.hostgroup.get({
            'output': ['name', 'groupid']
        })

        try:
            return res
        except (KeyError, IndexError) as e:
            logger.exception(e)
            raise ZabbixError(e)


class ZabbixNamedContainer(object):
    """
    Base class for ZabbixUserContainer etc.
    As ZabbixUserGroupContainer.users contains instances of ZabbixUserContainer instances, making it a set allows us
     to do useful operations with it. Therefore, we implemented this class so that those instances can be part of a set.
    """
    zabbix_id = None

    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return '{}(name={}) with zabbix_id {}'.format(self.__class__.__name__, self.name, self.zabbix_id)

    def __eq__(self, other):
        if hasattr(other, 'name') and issubclass(self.__class__, other.__class__):
            return self.name == other.name
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.name.__hash__()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        raise ValueError('Name is immutable')


class ZabbixUserContainer(ZabbixNamedContainer):
    """
    Container class for the Zabbix User object.
    """
    MEDIA_ENABLED = 0  # 0 - enabled, 1 - disabled [sic in zabbix docs]
    USER_QUERY_BASE = frozendict({'selectUsrgrps': ('usrgrpid', 'name', 'gui_access'),
                                  'selectMedias': ('mediatypeid', 'sendto')
                                  })
    _user = None

    def __init__(self, name, zapi=None):
        super(ZabbixUserContainer, self).__init__(name)
        self._zapi = zapi
        self.groups = set()
        self._api_response = None

    @classmethod
    def synchronize(cls, zapi, user):
        """
        We check whether the user object exists in zabbix. If not, we create it. If it does, we update it.
        """

        try:
            existing_zabbix_user = cls.from_zabbix_alias(zapi, user.username)
        except RemoteObjectDoesNotExist:
            existing_zabbix_user = None

        user_to_sync = cls.from_mgmt_data(zapi, user)

        if user_to_sync.groups and not existing_zabbix_user:  # Create
            user_to_sync.create()
        elif user_to_sync.groups and existing_zabbix_user:  # Update
            user_to_sync.zabbix_id = existing_zabbix_user.zabbix_id
            user_to_sync.update_all()
        elif not user_to_sync.groups and existing_zabbix_user:  # Delete
            user_to_sync.delete()
        elif not user_to_sync.groups and not existing_zabbix_user:  # No-op
            pass
        else:
            raise AssertionError('This should never happen')

    @classmethod
    def from_mgmt_data(cls, zapi, user):
        container = cls(name=user.username, zapi=zapi)
        container._user = user
        container.prepare_groups()
        return container

    @classmethod
    def from_zabbix_alias(cls, zapi, alias):
        response = zapi.user.get(dict(filter={'alias': alias}, **cls.USER_QUERY_BASE))

        if response:
            assert len(response) == 1, 'User mapping should be injective'
            return cls.from_zabbix_data(zapi, response[0])
        else:
            raise RemoteObjectDoesNotExist

    @classmethod
    def from_zabbix_id(cls, zapi, zabbix_id):
        response = zapi.user.get(dict(userids=zabbix_id, **cls.USER_QUERY_BASE))

        if response:
            assert len(response) == 1, 'User mapping should be injective'
            return cls.from_zabbix_data(zapi, response[0])
        else:
            raise RemoteObjectDoesNotExist

    @classmethod
    def from_zabbix_data(cls, zapi, api_response_object):
        assert api_response_object
        container = cls(name=api_response_object['alias'], zapi=zapi)

        container._api_response = api_response_object
        container.zabbix_id = api_response_object['userid']
        container._refresh_groups(api_response_object)
        return container

    @classmethod
    def delete_by_name(cls, zapi, name):
        zabbix_id = cls.fetch_zabbix_id(zapi, name)
        if zabbix_id:
            zapi.user.delete([zabbix_id])

    @staticmethod
    def delete_by_id(zapi, zabbix_id):
        zapi.user.delete([zabbix_id])

    @staticmethod
    def fetch_zabbix_id(zapi, username):
        response = zapi.user.get(dict(filter={'alias': username}))
        if not len(response):
            return None
        elif len(response) == 1:
            return response[0]['userid']
        else:
            raise ZabbixAPIError

    def renew_zabbix_id(self):
        self.zabbix_id = self.fetch_zabbix_id(self._zapi, self.name)

    def update_all(self):
        """
        When updating user in zabbix<3.4, two calls have to be done: first for updating user name and groups and
        second to update user media.
        """
        assert self.zabbix_id, 'A user in zabbix should be first created, then updated. %s has no zabbix_id.' % self
        user_update_request_content = self._get_api_request_object_stub()

        self._attach_group_membership(user_update_request_content)
        self._attach_basic_info(user_update_request_content)

        logger.debug('Updating user %s with group info and identity: %s', self.zabbix_id,
                     user_update_request_content)
        self._api_response = self._zapi.user.update(user_update_request_content)

        user_media_update_request_content = {'users': {'userid': self.zabbix_id}}
        self._attach_media_for_update_call(user_media_update_request_content)

        logger.debug('Updating user %s with media: %s', self.zabbix_id, user_media_update_request_content)
        self._api_response = self._zapi.user.updatemedia(user_media_update_request_content)

    def create(self):
        assert not self.zabbix_id, \
            '%s has the zabbix_id already and therefore you should try to update the object, not create it.' % self

        user_object = {}

        self._attach_group_membership(user_object)
        self._attach_media_for_create_call(user_object)
        self._attach_basic_info(user_object)

        user_object['alias'] = self._user.username
        user_object['passwd'] = self._user.__class__.objects.make_random_password(20)  # TODO let the user set it

        logger.debug('Creating user: %s', user_object)

        try:
            self._api_response = self._zapi.user.create(user_object)
        except ZabbixAPIError:
            # TODO perhaps we should ignore race condition errors, or repeat the task?
            # example: ZabbixAPIError: Application error....
            raise
        else:
            self.zabbix_id = self._api_response['userids'][0]

        return self

    def delete(self):
        if not self.zabbix_id:
            self.renew_zabbix_id()
        self.delete_by_id(self._zapi, self.zabbix_id)
        self.zabbix_id = None

    def _prepare_groups(self):
        yielded_owned_dcs = set()
        user_related_dcs = Dc.objects.filter(Q(owner=self._user) | Q(roles__user=self._user))

        for dc_name, group_name, user_id in user_related_dcs.values_list('name', 'roles__name', 'roles__user'):
            if user_id == self._user.id:
                local_group_name = group_name
            elif dc_name not in yielded_owned_dcs:
                local_group_name = ZabbixUserGroupContainer.OWNERS_GROUP
                yielded_owned_dcs.add(dc_name)
            else:
                continue

            qualified_group_name = ZabbixUserGroupContainer.user_group_name_factory(dc_name=dc_name,
                                                                                    local_group_name=local_group_name)
            try:
                yield ZabbixUserGroupContainer.from_zabbix_name(zapi=self._zapi,
                                                                name=qualified_group_name,
                                                                resolve_users=False)
            except RemoteObjectDoesNotExist:
                pass  # We don't create/delete user groups when users are created.

    def prepare_groups(self):
        self.groups = set(self._prepare_groups())

    def _refresh_groups(self, api_response):
        self.groups = set(
            ZabbixUserGroupContainer.from_zabbix_data(self._zapi, group) for group in api_response.get('usrgrps', [])
        )

    def refresh(self):
        response = self._zapi.user.get(dict(userids=self.zabbix_id, **self.USER_QUERY_BASE))
        if not response:
            raise ObjectManipulationError('%s doesn\'t exit anymore'.format(self))

        self._api_response = response[0]
        self._refresh_groups(self._api_response)
        # TODO refresh media etc

    def update_group_membership(self):
        assert self.zabbix_id, 'A user in zabbix should be first created, then updated. %s has no zabbix_id.' % self
        user_object = self._get_api_request_object_stub()
        self._attach_group_membership(user_object)
        logger.debug('Updating user: %s', user_object)
        self._api_response = self._zapi.user.update(user_object)

    def _attach_group_membership(self, api_request_object):
        zabbix_ids_of_all_user_groups = [group.zabbix_id for group in self.groups]
        assert self.groups and all(zabbix_ids_of_all_user_groups), \
            'To be able to attach groups (%s) to a user(%s), they all have to be in zabbix first.' % (
                self.groups, self)
        # This cannot be a set because it's serialized to json, which is not supported for sets:
        api_request_object['usrgrps'] = zabbix_ids_of_all_user_groups

    def _prepare_media(self):
        media = []
        for media_type in ZabbixMediaContainer.MEDIAS:
            user_media = getattr(self._user, 'get_alerting_{}'.format(media_type), None)
            if user_media:
                medium = {'mediatypeid': user_media.media_type,
                          'sendto': user_media.sendto,
                          'period': user_media.period,
                          'severity': user_media.severity,
                          'active': self.MEDIA_ENABLED}
                media.append(medium)
        return media

    def _attach_media_for_create_call(self, api_request_object):
        api_request_object['user_medias'] = self._prepare_media()

    def _attach_media_for_update_call(self, api_request_object):
        api_request_object['medias'] = self._prepare_media()

    def _attach_basic_info(self, api_request_object):
        api_request_object['name'] = self._user.first_name
        api_request_object['surname'] = self._user.last_name
        # user_object['type']= FIXME self._user.is_superadmin but we miss request

    def _get_api_request_object_stub(self):
        return {'userid': self.zabbix_id}


class ZabbixUserGroupContainer(ZabbixNamedContainer):
    """
    Container class for the Zabbix UserGroup object.
    """
    FRONTEND_ACCESS_ENABLED_WITH_DEFAULT_AUTH = '0'
    FRONTEND_ACCESS_DISABLED = '2'
    USERS_STATUS_ENABLED = 0
    PERMISSION_DENY = 0
    PERMISSION_READ_ONLY = 2
    PERMISSION_READ_WRITE = 3
    QUERY_BASE = frozendict({'selectUsers': ['alias'], 'limit': 1})
    QUERY_WITHOUT_USERS = {'limit': 1}
    OWNERS_GROUP = '#owner'
    USER_GROUP_NAME_MAX_LENGTH = 64

    def __init__(self, name, zapi=None):
        super(ZabbixUserGroupContainer, self).__init__(name)
        self._zapi = zapi
        self.users = set()
        self.host_groups = set()
        self.superuser_group = False
        self._api_response = None

    @classmethod
    def user_group_name_factory(cls, dc_name, local_group_name):
        """
        We have to qualify the dc name to prevent name clashing among groups in different datacenters,
        but in the same zabbix.
        """
        name = ':{}:{}:'.format(dc_name, local_group_name)
        if len(name) > cls.USER_GROUP_NAME_MAX_LENGTH:
            raise ValueError('dc_name + group name should have less than 62 chars, '
                             'but they have %d instead: %s %s' % (len(name), dc_name, local_group_name))
        return name

    @classmethod
    def from_zabbix_id(cls, zapi, zabbix_id):
        response = zapi.usergroup.get(dict(usrgrpids=[zabbix_id], **cls.QUERY_BASE))

        if response:
            return cls.from_zabbix_data(zapi, response[0])
        else:
            raise RemoteObjectDoesNotExist

    @classmethod
    def from_zabbix_name(cls, zapi, name, resolve_users=True):
        if resolve_users:
            query = cls.QUERY_BASE
        else:
            query = cls.QUERY_WITHOUT_USERS

        response = zapi.usergroup.get(dict(search={'name': name}, **query))

        if response:
            return cls.from_zabbix_data(zapi, response[0])
        else:
            raise RemoteObjectDoesNotExist

    @classmethod
    def from_mgmt_data(cls, zapi, group_name, users, accessible_hostgroups=(), superusers=False):
        # I should probably get all existing user ids for user names, and hostgroup ids for hostgroup names
        container = cls(name=group_name, zapi=zapi)
        container.users = {ZabbixUserContainer.from_mgmt_data(zapi, user) for user in users}
        container.host_groups = {ZabbixHostGroupContainer.from_mgmt_data(zapi, hostgroup)
                                 for hostgroup in accessible_hostgroups}  # self._get_or_create_groups
        container.superuser_group = superusers  # FIXME this information is not used anywhere by now

        return container

    @classmethod
    def from_zabbix_data(cls, zapi, zabbix_object):
        container = cls(name=zabbix_object['name'], zapi=zapi)
        container.zabbix_id = zabbix_object['usrgrpid']
        #  container.superuser_group = FIXME cannot determine from this data
        container.users = {ZabbixUserContainer.from_zabbix_data(zapi, userdata) for userdata in
                           zabbix_object.get('users', [])}
        return container

    @classmethod
    def synchronize(cls, zapi, group_name, users, accessible_hostgroups, superusers=False):
        """
        Make sure that in the end, there will be a user group with specified users in zabbix.
        :param group_name: should be the qualified group name (<DC>:<group name>:)
        """
        # TODO synchronization of superadmins should be in the DC settings
        # todo will hosts be added in the next step?
        user_group = ZabbixUserGroupContainer.from_mgmt_data(zapi,
                                                             group_name,
                                                             users,
                                                             accessible_hostgroups,
                                                             superusers)
        try:
            zabbix_user_group = ZabbixUserGroupContainer.from_zabbix_name(zapi, group_name, resolve_users=True)
        except RemoteObjectDoesNotExist:
            # We create it
            user_group.create()
        else:
            # Otherwise we update it
            zabbix_user_group.update_from(user_group)

    @staticmethod
    def delete_by_name(zapi, name):
        # for optimization: z.zapi.usergroup.get({'search': {'name': ":dc_name:*"}, 'searchWildcardsEnabled': True})
        try:
            group = ZabbixUserGroupContainer.from_zabbix_name(zapi, name)
        except RemoteObjectDoesNotExist:
            return
        else:
            group.delete()

    def delete(self):
        logger.debug('Going to delete group %s', self.name)
        logger.debug('Group.users before: %s', self.users)
        users_to_remove = self.users.copy()  # We have to copy it because group.users will get messed up
        self.remove_users(users_to_remove, delete_users_if_last=True)  # remove all users
        logger.debug('Group.users after: %s', self.users)
        self._zapi.usergroup.delete([self.zabbix_id])
        self.zabbix_id = None

    def create(self):
        assert not self.zabbix_id, \
            '%s has the zabbix_id already and therefore you should try to update the object, not create it.' % self

        user_group_object = {'name': self.name,
                             'users_status': self.USERS_STATUS_ENABLED,
                             'gui_access': self.FRONTEND_ACCESS_DISABLED,
                             'rights': [],
                             }

        if self.superuser_group:
            hostgroups_access_permission = self.PERMISSION_READ_WRITE
        else:
            hostgroups_access_permission = self.PERMISSION_READ_ONLY

        for host_group in self.host_groups:
            if not host_group.zabbix_id:
                raise ObjectManipulationError('Host group {} doesn\'t exist in zabbix yet, '
                                              'it has to be created first'.format(host_group.name))

            user_group_object['rights'].append({'permission': hostgroups_access_permission,
                                                'id': host_group.zabbix_id})

        logger.debug('Creating usergroup: %s', user_group_object)
        self._api_response = self._zapi.usergroup.create(user_group_object)
        self.zabbix_id = self._api_response['usrgrpids'][0]

        user_group_object['userids'] = []
        self._refetch_users()
        self._push_current_users()

    def _refresh_users(self, api_response):
        self.users = {
            ZabbixUserContainer.from_zabbix_data(self._zapi, userdata) for userdata in api_response.get('users', [])
        }

    def refresh(self):
        response = self._zapi.usergroup.get(dict(usrgrpids=self.zabbix_id, **self.QUERY_BASE))

        if not response:
            raise ObjectManipulationError('%s doesn\'t exit anymore'.format(self))

        self._api_response = response[0]
        self._refresh_users(self._api_response)

    def update_superuser_status(self, superuser_group):
        if self.superuser_group != superuser_group:
            self.superuser_group = superuser_group
            self.update_hostgroup_info()  # There is some hostgroup information depending on the superuser status

    def update_hostgroup_info(self):
        logger.debug('TODO host group update %s', self.name)
        # TODO

    def update_users(self, user_group):
        logger.debug('synchronizing %s', self)
        logger.debug('remote_user_group.users %s', self.users)
        logger.debug('source_user_group.users %s', user_group.users)
        redundant_users = self.users - user_group.users
        logger.debug('redundant_users: %s', redundant_users)
        missing_users = user_group.users - self.users
        logger.debug('missing users: %s', missing_users)
        self.remove_users(redundant_users, delete_users_if_last=True)
        self.add_users(missing_users)

    def update_basic_information(self, user_group):
        self.update_superuser_status(user_group.superuser_group)

    def update_from(self, user_group):
        self.update_users(user_group)
        self.update_basic_information(user_group)
        logger.debug('todo hostgroups')

    def _refetch_users(self):
        for user in self.users:
            user.renew_zabbix_id()
            user.groups.add(self)
            if not user.zabbix_id:
                try:
                    user.create()
                except ZabbixAPIException:
                    user.renew_zabbix_id()

    def add_users(self, new_users):
        self.users.update(new_users)
        self._refetch_users()
        self._push_current_users()

    def _push_current_users(self):
        self._zapi.usergroup.update({'usrgrpid': self.zabbix_id,
                                     'userids': [user.zabbix_id for user in self.users]}
                                    )

    def remove_user(self, user, delete_user_if_last=False):
        user.refresh()

        if self not in user.groups:
            logger.warn('User is not in the group: %s %s (possible race condition)', self, user.groups)

        if not user.groups - {self} and not delete_user_if_last:
            raise ObjectManipulationError('Cannot remove the last group (%s) '
                                          'without deleting the user %s itself!' % (self, user))

        user.groups -= {self}

        if user.groups:
            user.update_group_membership()
        else:
            user.delete()

    def remove_users(self, redundant_users, delete_users_if_last):  # TODO move
        self.users -= redundant_users
        # Some zabbix users has to be deleted as this is their last group. We have to go the slower way.
        for user in redundant_users:
            self.remove_user(user, delete_user_if_last=delete_users_if_last)
            # TODO create also a faster way of removal for users that has also different groups


class ZabbixHostGroupContainer(ZabbixNamedContainer):
    """
    Container class for the Zabbix HostGroup object.
    Incomplete, TODO
    """
    RE_NAME_WITH_DC_PREFIX = re.compile(r'^:(?P<dc>.*):(?P<hostgroup>.+):$')
    zabbix_id = None

    def __init__(self, name, zapi=None):
        super(ZabbixHostGroupContainer, self).__init__(name)
        self._zapi = zapi

    @classmethod
    def from_mgmt_data(cls, name, zapi):
        container = cls(name, zapi)
        container._zapi = zapi
        response = zapi.hostgroup.get({'filter': {'name': name}})
        if response:
            assert len(response) == 1, 'Hostgroup name => locally generated hostgroup name mapping should be injective'
            container._zabbix_response = response[0]
        container.zabbix_id = container._zabbix_response['groupid']
        return container

    @staticmethod
    def hostgroup_name_factory(hostgroup_name, dc_name=''):
        if dc_name:
            name = ':{}:{}:'.format(dc_name, hostgroup_name)
        else:
            name = hostgroup_name

        return name

    def create(self):
        response = self._zapi.hostgroup.create({
                'name': self.name,
        })
        self.zabbix_id = response['groupids'][0]
        return self


class ZabbixMediaContainer(object):
    """
    Container class for the Zabbix HostGroup object.
    """
    SEVERITY_NOT_CLASSIFIED = 0  # TODO move to constants
    SEVERITY_INFORMATION = 1
    SEVERITY_WARNING = 2
    SEVERITY_AVERAGE = 3
    SEVERITY_HIGH = 4
    SEVERITY_DISASTER = 5
    SEVERITIES = (
        SEVERITY_NOT_CLASSIFIED, SEVERITY_INFORMATION, SEVERITY_WARNING, SEVERITY_AVERAGE, SEVERITY_HIGH,
        SEVERITY_DISASTER
    )
    # TODO Time is in UTC and therefore we should adjust this for the user's timezone
    PERIOD_DEFAULT_WORKING_HOURS = '1-5,09:00-18:00'
    PERIOD_DEFAULT = '1-7,00:00-24:00'
    MEDIAS = frozendict({
        'email': 1,
        'phone': 2,
        'xmpp': 3
    })  # todo is this static or is it defined somewhere?

    def __init__(self, media_type, sendto, severities, period):
        self.media_type = media_type
        self.sendto = sendto
        self.severity = self.media_severity_generator(severities)
        self.period = period

    @classmethod
    def media_severity_generator(cls, active_severities):
        """
        :param active_severities: (SEVERITY_WARNING, SEVERITY_HIGH)
        :return: number to be used as input for media.severity
        """
        result = 0
        for severity in active_severities:
            assert severity in cls.SEVERITIES
            result += 2 ** severity
        return result
