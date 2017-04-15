from time import time
from logging import getLogger, DEBUG, INFO, WARNING, ERROR, CRITICAL
from datetime import datetime
from subprocess import call
from django.conf import settings as django_settings
from django.core.cache import cache
from django.utils.six import iteritems
from frozendict import frozendict

from zabbix_api import ZabbixAPI, ZabbixAPIException
from api.decorators import catch_exception
from vms.models import DefaultDc

logger = getLogger(__name__)

_VM_KWARGS = (
    ('ostype', 1),
    ('ostype_text', 'test'),
    ('dc_name', 'test'),
    ('disk_image', 'test'),
    ('disk_image_abbr', 'test'),
)

VM_KWARGS = frozendict(_VM_KWARGS)
VM_KWARGS_KEYS = tuple(VM_KWARGS.keys())
VM_KWARGS_NIC = frozendict(_VM_KWARGS + (('net', 1), ('nic_id', 2)))
VM_KWARGS_DISK = frozendict(_VM_KWARGS + (('disk', 1), ('disk_id', 2)))
NODE_KWARGS = frozendict()
NODE_KWARGS_KEYS = tuple(NODE_KWARGS.keys())
RESULT_CACHE_TIMEOUT = 3600

__ZABBIX__ = {}  # This hold an instance of zabbix per DC


# noinspection PyPep8Naming
def getZabbix(dc, **kwargs):
    """
    Quick access to Zabbix instance.
    """
    global __ZABBIX__

    if dc.id in __ZABBIX__:
        return __ZABBIX__[dc.id]

    zx = Zabbix(dc, **kwargs)

    if zx.connected:
        __ZABBIX__[dc.id] = zx

    return zx


# noinspection PyPep8Naming
def delZabbix(dc):
    """
    Remove Zabbix instance from global cache.
    """
    global __ZABBIX__

    if dc.id in __ZABBIX__:
        del __ZABBIX__[dc.id]
        return True
    return False


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


class ZabbixError(Exception):
    """
    Custom zabbix exception - used only as wrapper.
    """
    pass


class FakeDetailLog(object):
    """
    Dummy list-like object used for collecting log lines.
    """
    def add(self, *args):
        pass
LOG = FakeDetailLog()


class _Zabbix(object):
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

    def _get_groups(self, obj_kwargs, hostgroup, hostgroups=(), log=None):
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

            if isinstance(name, int):
                gids.add(name)
            else:
                try:
                    gids.add(int(self._zabbix_get_groupid(name.format(**obj_kwargs))))
                except ZabbixError:
                    log(ERROR, 'Could not fetch zabbix hostgroup id for hostgroup "%s"', name)
                    continue

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

    def _diff_host(self, obj, host, interface, groups=(), templates=(), macros=None, status=HOST_MONITORED,
                   proxy_id=NO_PROXY):
        """Compare DB object and host (Zabbix) configuration and create an update dict; Issue #chili-331"""

        # Empty params means no update is needed
        params = {}

        # There should be one zabbix agent interface
        hi = None
        try:
            interfaces = self._parse_host_interfaces(host)

            for i, iface in enumerate(interfaces):
                if int(iface['type']) == self.HOSTINTERFACE_AGENT and int(iface['main']) == self.YES:
                    if hi:
                        # noinspection PyProtectedMember
                        raise ZabbixAPIException('Zabbix host ID "%s" for %s %s has multiple Zabbix Agent '
                                                 'configurations' % (host['hostid'], obj._meta.verbose_name_raw, obj))

                    # Zabbix host interface found, let's check it out
                    hi = iface

                    if (iface['dns'] != interface['dns'] or iface['ip'] != interface['ip'] or
                            str(iface['port']) != str(interface['port']) or
                            str(iface['useip']) != str(interface['useip'])):
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

        # Check zabbix host ID (name)
        host_id = self.host_id(obj)

        if host['host'] != host_id:
            params['host'] = host_id

        # Check zabbix visible name
        host_name = self.host_name(obj)

        if host['name'] != host_name:
            # Hostname changed! -> update name
            params['name'] = host_name

        # Check zabbix proxy ID
        proxy_hostid = int(host.get('proxy_hostid', self.NO_PROXY))

        if proxy_hostid != proxy_id:
            params['proxy_hostid'] = proxy_id

        # Always set to monitored (because this tasks is also run after deploying VM, which had monitoring disabled)
        if int(host['status']) != status:
            # Status changed! -> update status
            params['status'] = status

        # Always replace current zabbix templates with configured templates
        zx_templates = self._parse_host_templates(host)
        new_templates = set(templates)

        if zx_templates != new_templates:
            # Templates configuration changed!
            params['templates'] = self._gen_host_templates(new_templates)
            # Removed templates need to be cleared properly
            removed_templates = zx_templates - new_templates

            if removed_templates:
                params['templates_clear'] = self._gen_host_templates(removed_templates)

        # Always replace current zabbix groups with configured groups
        zx_groups = self._parse_host_groups(host)
        new_groups = set(groups)

        if zx_groups != new_groups:
            # Groups configuration changed!
            params['groups'] = self._gen_host_groups(new_groups)

        # Replace macros only if specified
        if macros is not None:
            zx_macros = self._parse_host_macros(host)

            if zx_macros != macros:
                # Host macros changed!
                params['macros'] = self._gen_host_macros(macros)

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

    def get_history(self, host, items, history, since, until, items_search=None):
        """Return monitoring history for selected zabbix host, items and period"""
        res = {'history': []}
        now = int(datetime.now().strftime('%s'))
        max_period = self.settings.MON_ZABBIX_GRAPH_MAX_PERIOD
        max_history = now - self.settings.MON_ZABBIX_GRAPH_MAX_HISTORY
        period = until - since
        since_history = None
        until_history = None
        since_trend = None
        until_trend = None

        if until < max_history or period > max_period:  # trends only
            until_trend = until
            since_trend = since
        else:  # history only
            until_history = until
            since_history = since

        try:
            res['items'] = self._zabbix_get_items(host, items, search_params=items_search)

            if not res['items']:
                raise ZabbixAPIException('Cannot find items for selected host in Zabbix')

            # noinspection PyTypeChecker
            params = {
                'itemids': [i['itemid'] for i in res['items']],
                'history': history,
                'sortfield': 'clock',
                'sortorder': 'ASC',
                'output': 'extend',
            }

            if since_trend and until_trend:
                params['time_from'] = since_trend
                params['time_till'] = until_trend
                res['history'] = self.zapi.trend.get(params)

            if since_history and until_history:
                params['time_from'] = since_history
                params['time_till'] = until_history
                res['history'] += self.zapi.history.get(params)

        except ZabbixAPIException as exc:
            self.log(ERROR, 'Zabbix API Error in get_history(%s, %s): %s', host, items, exc)
            raise ZabbixError('Zabbix API Error while retrieving history (%s)' % exc)

        else:
            return res


class InternalZabbix(_Zabbix):
    """
    Internal zabbix (monitoring from outside/node).
    """
    _obj_host_id_attr = 'zabbix_id'
    _obj_host_name_attr = 'zabbix_name'
    _obj_host_info_attr = 'zabbix_info'
    _obj_host_save_method = 'save_zabbix_info'

    def _vm_host_interface(self, vm):
        """Return host interface dict for a VM"""
        return self._get_host_interface(vm.node.hostname, vm.node.address)

    def _node_host_interface(self, node):
        """Return host interface dict for a VM"""
        return self._get_host_interface(node.hostname, node.address)

    # noinspection PyProtectedMember
    def _vm_groups(self, vm, log=None):
        """Return set of zabbix hostgroup IDs for a VM"""
        return self._get_groups(self._vm_kwargs(vm), django_settings._MON_ZABBIX_HOSTGROUP_VM,
                                django_settings._MON_ZABBIX_HOSTGROUPS_VM, log=log)

    def _node_groups(self, node, log=None):
        """Return set of zabbix hostgroup IDs for a Compute node"""
        hostgroups = set(self.settings.MON_ZABBIX_HOSTGROUPS_NODE)
        hostgroups.update(node.monitoring_hostgroups)

        return self._get_groups(self._node_kwargs(node), self.settings.MON_ZABBIX_HOSTGROUP_NODE, hostgroups, log=log)

    # noinspection PyProtectedMember
    def _vm_templates(self, vm, log=None):
        """Return set of zabbix template IDs for a VM"""
        vm_kwargs = self._vm_kwargs(vm)
        tids = self._get_templates(vm_kwargs, django_settings._MON_ZABBIX_TEMPLATES_VM, log=log)
        tids.update(self._get_vm_nic_templates(vm, vm_kwargs, django_settings._MON_ZABBIX_TEMPLATES_VM_NIC, log=log))
        tids.update(self._get_vm_disk_templates(vm, vm_kwargs, django_settings._MON_ZABBIX_TEMPLATES_VM_DISK, log=log))

        return tids

    def _node_templates(self, node, log=None):
        """Return set of zabbix template IDs for a Compute node"""
        # noinspection PyProtectedMember
        templates = set(django_settings._MON_ZABBIX_TEMPLATES_NODE)
        templates.update(self.settings.MON_ZABBIX_TEMPLATES_NODE)
        templates.update(node.monitoring_templates)

        return self._get_templates(self._node_kwargs(node), templates, log=log)

    # noinspection PyMethodMayBeStatic
    def _vm_macros(self, vm):
        """Return dict of internal macros for a VM"""
        return {
            '{$VCPUS}': str(vm.vcpus_active),
            '{$RAM}': str(vm.ram_active),
            '{$ZONEID}': str(vm.zoneid),
        }

    # noinspection PyMethodMayBeStatic
    def _node_macros(self, node):
        """Return dict of internal macros for a compute node"""
        return {
            '{$CPU_COUNT}': str(node.cpu),
        }

    def node_host_status(self, node):
        """Helper method for synchronization of zabbix host status according to node status"""
        if node.is_online() or node.is_unreachable():
            return self.HOST_MONITORED
        else:
            return self.HOST_UNMONITORED

    def create_vm_host(self, vm, log=None):
        """Create new Zabbix host from VM object"""
        return self._create_host(vm, self._vm_host_interface(vm), groups=self._vm_groups(vm, log=log),
                                 templates=self._vm_templates(vm, log=log), macros=self._vm_macros(vm), log=log)

    def create_node_host(self, node, log=None):
        """Create new Zabbix host from Node object"""
        return self._create_host(node, self._node_host_interface(node), groups=self._node_groups(node, log=log),
                                 templates=self._node_templates(node, log=log), macros=self._node_macros(node),
                                 status=self.node_host_status(node), log=log)

    def diff_vm_host(self, vm, host, log=None):
        """Compare VM (DB) and host (Zabbix) configuration and create an update dict"""
        return self._diff_host(vm, host, self._vm_host_interface(vm), groups=self._vm_groups(vm, log=log),
                               templates=self._vm_templates(vm, log=log), macros=self._vm_macros(vm))

    def diff_node_host(self, node, host, log=None):
        """Compare Node (DB) and host (Zabbix) configuration and create an update dict"""
        return self._diff_host(node, host, self._node_host_interface(node), groups=self._node_groups(node, log=log),
                               templates=self._node_templates(node, log=log), macros=self._node_macros(node),
                               status=self.node_host_status(node))

    def node_get_sla(self, node_hostname, since, till):
        """Retrieve compute node's SLA for time period defined by since and till arguments"""
        try:
            serviceid = self._zabbix_get_serviceid(node_hostname)
            sla = float(self._zabbix_get_sla(serviceid, since, till))
        except ZabbixAPIException as exc:
            err = 'Zabbix API Error when retrieving SLA (%s)' % exc
            self.log(ERROR, err)
            raise ZabbixError(err)
        except ZabbixError as exc:
            err = 'Could not parse Zabbix API output when retrieving SLA (%s)' % exc
            self.log(ERROR, err)
            raise ZabbixError(err)

        return sla

    def vm_get_sla(self, vm_node_history):
        """Retrieve SLA from VMs node_history list"""
        sla = float(0)

        for i in vm_node_history:
            try:
                serviceid = self._zabbix_get_serviceid(i['node_hostname'])
                node_sla = self._zabbix_get_sla(serviceid, i['since'], i['till'])
            except ZabbixAPIException as exc:
                err = 'Zabbix API Error when retrieving SLA (%s)' % exc
                self.log(ERROR, err)
                raise ZabbixError(err)
            except ZabbixError as exc:
                err = 'Could not parse Zabbix API output when retrieving SLA (%s)' % exc
                self.log(ERROR, err)
                raise ZabbixError(err)
            else:
                sla += float(node_sla) * i['weight']

        return sla

    def send_alert(self, host, msg, priority=_Zabbix.NOT_CLASSIFIED, include_signature=True):
        """Send alert by pushing data into custom alert items"""
        priority = int(priority)

        if not (self.NOT_CLASSIFIED <= priority <= self.DISASTER):
            raise ValueError('Invalid priority')

        item = self.CUSTOM_ALERT_ITEM

        if priority == self.NOT_CLASSIFIED:
            self.log(WARNING, 'Alert with "not classified" priority may not send any notification')
        else:
            item += str(priority)

        if include_signature:
            msg += ' \n--\n' + self.settings.SITE_SIGNATURE

        self.log(INFO, 'Sending zabbix alert to host "%s" and item "%s" with message "%s"', host, item, msg)

        return self._send_data(host, item, msg)

    # noinspection PyProtectedMember
    @catch_exception
    def create_node_service(self, node):
        """Create Zabbix IT Service for a Compute node.
        This operation is performed along with node creation in Zabbix, therefore it should fail silently"""
        hostid = self.get_hostid(node)
        parentid = self._zabbix_get_serviceid(django_settings._MON_ZABBIX_ITS_PARENT_NODE)

        # Create node IT service
        serviceid = self._create_service(self.host_name(node), parentid, algorithm=self.PROBLEM_ALL)

        # Attach trigger dependencies to node IT service
        for name, desc in django_settings._MON_ZABBIX_ITS_TRIGGERS_NODE:
            triggerid = self._zabbix_get_triggerid(hostid, desc)
            self._create_service(name, serviceid, algorithm=self.PROBLEM_ONE, triggerid=triggerid)

        return serviceid

    @catch_exception
    def update_node_service(self, node_hostname, **params):
        """Update Zabbix IT Service for a Compute node (hostname change)."""
        serviceid = self._zabbix_get_serviceid(node_hostname)

        return self._update_service(serviceid=serviceid, **params)

    @catch_exception
    def delete_node_service(self, zabbix_name):
        """Delete Zabbix IT Service for a Compute node.
        This operation is performed along with node removal from Zabbix, therefore it should fail silently"""
        serviceid = self._zabbix_get_serviceid(zabbix_name)
        child_serviceids = self._zabbix_get_children_serviceids(serviceid)

        # First delete all children
        for i in child_serviceids:
            try:
                self.zapi.service.delete([i])
            except ZabbixAPIException as e:
                logger.exception(e)

        # Finally delete the node IT service
        try:
            res = self.zapi.service.delete([serviceid])
            return res['serviceids'][0]
        except (ZabbixAPIException, KeyError, IndexError) as e:
            logger.exception(e)
            raise ZabbixError(e)


class ExternalZabbix(_Zabbix):
    """
    Application zabbix per DC (monitoring from inside/VM agent).
    """
    _obj_host_id_attr = 'external_zabbix_id'
    _obj_host_name_attr = 'external_zabbix_name'
    _obj_host_info_attr = 'external_zabbix_info'
    _obj_host_save_method = 'save_external_zabbix_info'

    @property
    def login_error(self):
        return cache.get(self._log_prefix)

    @login_error.setter
    def login_error(self, value):
        if value:
            cache.set(self._log_prefix, value)
        else:
            cache.delete(self._log_prefix)

    def _vm_host_interface(self, vm):
        """Return host interface dict for a VM"""
        return self._get_host_interface(vm.monitoring_dns, vm.monitoring_ip, port=vm.monitoring_port,
                                        useip=vm.monitoring_useip)

    def _vm_proxy_id(self, vm):
        """Return proxy ID for a VM or 0"""
        return self._get_proxy_id(vm.monitoring_proxy)

    def _vm_groups(self, vm, log=None):
        """Return set of zabbix hostgroup IDs for a VM"""
        hostgroups = set(self.settings.MON_ZABBIX_HOSTGROUPS_VM)
        hostgroups.update(vm.monitoring_hostgroups)

        return self._get_groups(self._vm_kwargs(vm), self.settings.MON_ZABBIX_HOSTGROUP_VM, hostgroups, log=log)

    def _vm_templates(self, vm, log=None):
        """Return set of zabbix template IDs for a VM"""
        vm_kwargs = self._vm_kwargs(vm)
        settings = self.settings
        templates = set(settings.MON_ZABBIX_TEMPLATES_VM)
        templates.update(vm.monitoring_templates)

        tids = self._get_templates(vm_kwargs, templates, log=log)
        tids.update(self._get_vm_nic_templates(vm, vm_kwargs, settings.MON_ZABBIX_TEMPLATES_VM_NIC, log=log))
        tids.update(self._get_vm_disk_templates(vm, vm_kwargs, settings.MON_ZABBIX_TEMPLATES_VM_DISK, log=log))

        if settings.MON_ZABBIX_TEMPLATES_VM_MAP_TO_TAGS:
            tids_by_tags = self._get_templates_by_tags(vm.tag_list)

            if tids_by_tags:
                _log = log or self.log

                if settings.MON_ZABBIX_TEMPLATES_VM_RESTRICT:
                    allowed_tids = self._get_templates(vm_kwargs, settings.MON_ZABBIX_TEMPLATES_VM_ALLOWED, log=log)
                    restricted_tids = tids_by_tags.difference(allowed_tids)

                    if restricted_tids:
                        tids_by_tags = tids_by_tags.intersection(allowed_tids)
                        _log(WARNING, 'VM %s is not allowed to use following templates mapped from VM tags: %s',
                             vm, restricted_tids)

                _log(INFO, 'VM %s is going to use following templates mapped from VM tags: %s', vm, tids_by_tags)
                tids.update(tids_by_tags)

        return tids

    def create_vm_host(self, vm, log=None):
        """Create new Zabbix host from VM object"""
        return self._create_host(vm, self._vm_host_interface(vm), groups=self._vm_groups(vm, log=log),
                                 templates=self._vm_templates(vm, log=log))

    def diff_vm_host(self, vm, host, log=None):
        """Compare VM (DB) and host (Zabbix) configuration and create an update dict"""
        return self._diff_host(vm, host, self._vm_host_interface(vm), groups=self._vm_groups(vm, log=log),
                               templates=self._vm_templates(vm, log=log), proxy_id=self._vm_proxy_id(vm))


class Zabbix(object):
    """
    Public Zabbix class used via getZabbix() and delZabbix() functions.
    """
    zbx = _Zabbix

    def __init__(self, dc, **kwargs):
        self.dc = dc

        # InternalZabbix need default DC, which can be the same as the dc parameter
        if dc.is_default():
            default_dc = dc
            dcns = dc1s = dc.settings
            reuse_zapi = True
        else:
            default_dc = DefaultDc()
            # Reuse zabbix connection if the server and username did not change
            dcns, dc1s = dc.settings, default_dc.settings
            reuse_zapi = (dcns.MON_ZABBIX_SERVER == dc1s.MON_ZABBIX_SERVER and
                          dcns.MON_ZABBIX_USERNAME == dc1s.MON_ZABBIX_USERNAME)

        self.izx = InternalZabbix(dc1s, name=default_dc.name, **kwargs)

        if reuse_zapi:
            kwargs['zapi'] = self.izx.zapi

        self.ezx = ExternalZabbix(dcns, name=dc.name, **kwargs)

    @property
    def connected(self):
        """We are connected only if both zabbix objects are connected"""
        return self.izx.connected and self.ezx.connected

    def reset_cache(self):
        """Clear cache for both zabbix objects"""
        self.izx.reset_cache()
        self.ezx.reset_cache()

    @classmethod
    @catch_exception
    def vm_send_alert(cls, vm, msg, priority=_Zabbix.HIGH, **kwargs):
        """[INTERNAL] Convenient shortcut for sending VM related alerts"""
        dc = vm.dc
        dcs = dc.settings

        if not (dcs.MON_ZABBIX_ENABLED and vm.is_zabbix_sync_active()):
            logger.warning('Not sending alert for VM %s, because it has monitoring disabled', vm)
            return

        if vm.is_notcreated():
            logger.warning('Not sending alert for VM %s, because it is not created', vm)
            return

        izx = getZabbix(dc).izx  # InternalZabbix from cache

        return izx.send_alert(izx.host_id(vm), msg, priority=priority, **kwargs)

    @classmethod
    @catch_exception
    def node_send_alert(cls, node, msg, priority=_Zabbix.HIGH, **kwargs):
        """[INTERNAL] Convenient shortcut for sending Node related alerts"""
        dc = DefaultDc()
        dcs = dc.settings

        if not (dcs.MON_ZABBIX_ENABLED and dcs.MON_ZABBIX_NODE_SYNC):  # dc1_settings
            logger.warning('Not sending alert for Node %s, because global node monitoring disabled', node)
            return

        if node.is_online():
            logger.warning('Not sending alert for Node %s, because it is not online', node)
            return

        izx = getZabbix(dc).izx

        return izx.send_alert(izx.host_id(node), msg, priority=priority, **kwargs)

    def vm_sla(self, vm_node_history):
        """[INTERNAL] Return SLA (%) for VM.node_history and selected time period; Returns None in case of problems"""
        return self.izx.vm_get_sla(vm_node_history)

    def vm_history(self, vm_host_id, items, zhistory, since, until, items_search=None):
        """[INTERNAL] Return VM history data for selected graph and period"""
        return self.izx.get_history(vm_host_id, items, zhistory, since, until, items_search=items_search)

    @staticmethod
    def _vm_disable_sync(zx, vm, log=None):
        """[INTERNAL+EXTERNAL] Cleanup VM zabbix stuff after zabbix monitoring was disabled on VM"""
        log = log or zx.log
        hostid = zx.host_info(vm).get('hostid', None)

        if hostid:  # zabbix_sync is disabled, but was previously enabled => delete host from zabbix
            log(INFO, 'Zabbix synchronization switched to disabled for VM %s', vm)
            log(WARNING, 'Deleting Zabbix host ID "%s" for VM %s', hostid, vm)

            if zx.delete_host(hostid, log=log):
                log(INFO, 'Deleted Zabbix host ID "%s"', hostid)
                zx.save_host_info(vm, host={}, log=log)  # TODO: check this, changed from: zx.host_save(vm, {})
                return True
            else:
                log(ERROR, 'Could not delete Zabbix host ID "%s"', hostid)
                return False
        else:
            log(INFO, 'Zabbix synchronization disabled for VM %s', vm)
            return None

    @staticmethod
    def _vm_create_host(zx, vm, log=None):
        """[INTERNAL+EXTERNAL] Create new host in for VM"""
        log = log or zx.log
        log(WARNING, 'VM %s is not defined in Zabbix. Creating...', vm)
        hostid = zx.create_vm_host(vm, log=log)

        if hostid:
            log(INFO, 'Created new Zabbix host ID "%s" for VM %s', hostid, vm)
            zx.save_host_info(vm, log=log)
            return True
        else:
            log(ERROR, 'Could not create new Zabbix host for VM %s', vm)
            return False

    @staticmethod
    def _vm_update_host(zx, vm, host, log=None):
        """[INTERNAL+EXTERNAL] Update host configuration according to VM changes"""
        log = log or zx.log
        hostid = host['hostid']
        log(DEBUG, 'VM %s already defined in Zabbix as host ID "%s"', vm, hostid)
        params = zx.diff_vm_host(vm, host, log=log)  # Issue #chili-311

        if params:
            log(WARNING, 'Zabbix host ID "%s" configuration differs from current VM %s configuration', hostid, vm)
            log(INFO, 'Updating Zabbix host ID "%s" according to VM %s with following parameters: %s',
                hostid, vm, params)

            if zx.update_host(hostid, log=log, **params):
                log(INFO, 'Updated Zabbix host ID "%s"', hostid)
                zx.save_host_info(vm, log=log)
            else:
                log(ERROR, 'Could not update Zabbix host ID "%s"', hostid)
                return False

        else:  # Host in sync with VM
            log(INFO, 'Zabbix host ID "%s" configuration is synchronized with current VM %s configuration', hostid, vm)
            return True

        return True

    @staticmethod
    def _vm_disable_host(zx, vm, log=None):
        """[INTERNAL+EXTERNAL] Switch VM host status in zabbix to not monitored"""
        log = log or zx.log
        hostid = zx.get_hostid(vm, log=log)

        if not hostid:
            log(ERROR, 'Zabbix host for VM %s does not exist!', vm)
            return False

        log(WARNING, 'Setting Zabbix host ID "%s" status to unmonitored for VM %s', hostid, vm)

        if zx.update_host(hostid, log=log, status=zx.HOST_UNMONITORED):
            log(INFO, 'Updated Zabbix host ID "%s" status to unmonitored', hostid)
            zx.save_host_info(vm, log=log)
            return True
        else:
            log(ERROR, 'Could not update Zabbix host ID "%s" status to unmonitored', hostid)
            return False

    @staticmethod
    def _vm_delete_host(zx, vm, log=None):
        """[INTERNAL+EXTERNAL] Delete one VM zabbix host"""
        log = log or zx.log
        vm_uuid = zx.host_id(vm)
        host = zx.get_host(vm_uuid, log=log)

        if not host:
            log(WARNING, 'Zabbix host for VM %s does not exist!', vm_uuid)
            return False

        hostid = host['hostid']
        log(WARNING, 'Deleting Zabbix host ID "%s" for VM %s', hostid, vm_uuid)

        if zx.delete_host(hostid, log=log):
            log(INFO, 'Deleted Zabbix host ID "%s"', hostid)
            return True
        else:
            log(ERROR, 'Could not delete Zabbix host ID "%s"', hostid)
            return False

    def is_vm_host_created(self, vm):
        """[INTERNAL] Check if VM host is created in zabbix"""
        return vm.is_zabbix_sync_active() and self.izx.has_host_info(vm)

    def vm_sync(self, vm, force_update=False, task_log=LOG):
        """[INTERNAL+EXTERNAL] Create or update zabbix host in internal and external zabbix"""
        dc_settings = vm.dc.settings
        result = []

        # noinspection PyProtectedMember
        for zx_sync, vm_sync, zx in ((vm.is_zabbix_sync_active(), dc_settings._MON_ZABBIX_VM_SYNC, self.izx),
                                     (vm.is_external_zabbix_sync_active(), dc_settings.MON_ZABBIX_VM_SYNC, self.ezx)):
            log = zx.get_log_fun(task_log)

            if zx_sync:
                if force_update and zx.has_host_info(vm):
                    host = zx.host_info(vm)
                else:
                    host = zx.get_host(zx.host_id(vm), log=log)

                if host:
                    # Update host only if something changed
                    result.append(self._vm_update_host(zx, vm, host, log=log))
                elif force_update:
                    log(WARNING, 'Could not update zabbix host for VM %s, because it is not defined in Zabbix', vm)
                    result.append(False)
                else:
                    if vm_sync:
                        # Host does not exist in Zabbix, so we have to create it
                        result.append(self._vm_create_host(zx, vm, log=log))
                    else:
                        log(INFO, 'Zabbix synchronization disabled for VM %s in DC %s', vm, vm.dc)
                        result.append(None)
            else:
                result.append(self._vm_disable_sync(zx, vm, log=log))

        return result

    def vm_disable(self, vm, task_log=LOG):
        """[INTERNAL+EXTERNAL] Switch host status in zabbix to not monitored in internal and external zabbix"""
        result = []
        izx_log = self.izx.get_log_fun(task_log)
        ezx_log = self.ezx.get_log_fun(task_log)

        if vm.is_zabbix_sync_active():
            result.append(self._vm_disable_host(self.izx, vm, log=izx_log))
        else:
            izx_log(INFO, 'Internal zabbix synchronization disabled for VM %s', vm)
            result.append(None)

        if vm.is_external_zabbix_sync_active():
            result.append(self._vm_disable_host(self.ezx, vm, log=ezx_log))
        else:
            ezx_log(INFO, 'External zabbix synchronization disabled for VM %s', vm)
            result.append(None)

        return result

    def vm_delete(self, vm, internal=True, external=True, task_log=LOG):
        """[INTERNAL+EXTERNAL] Delete VM zabbix host from internal and external zabbix"""
        result = []
        izx_log = self.izx.get_log_fun(task_log)
        ezx_log = self.ezx.get_log_fun(task_log)

        if internal:
            result.append(self._vm_delete_host(self.izx, vm, log=izx_log))
        else:
            izx_log(INFO, 'Internal zabbix synchronization disabled for VM %s', vm.uuid)
            result.append(None)

        if external:
            result.append(self._vm_delete_host(self.ezx, vm, log=ezx_log))
        else:
            ezx_log(INFO, 'External zabbix synchronization disabled for VM %s', vm.uuid)
            result.append(None)

        return result

    def node_sla(self, node_hostname, since, until):
        """[INTERNAL] Return SLA (%) for compute node and selected time period; Returns None in case of problems"""
        return self.izx.node_get_sla(node_hostname, since, until)

    def node_sync(self, node, task_log=LOG):
        """[INTERNAL] Create or update zabbix host related to compute node"""
        zx = self.izx
        log = zx.get_log_fun(task_log)
        host = zx.get_host(zx.host_id(node), log=log)

        if not host:  # Host does not exist in Zabbix, so we have to create it
            log(WARNING, 'Node %s is not defined in Zabbix. Creating...', node)
            hostid = zx.create_node_host(node, log=log)

            if hostid:
                log(INFO, 'Created new Zabbix host ID "%s" for Node %s', hostid, node)
                zx.save_host_info(node, log=log)
                its = zx.create_node_service(node)

                if its:
                    log(INFO, 'Create new Zabbix IT Service ID "%s" for Node %s', its, node)
                else:
                    log(ERROR, 'Could not create new Zabbix IT Services for Node %s', node)

                return True

            else:
                log(ERROR, 'Could not create new Zabbix host for Node %s', node)

            return False

        hostid = host['hostid']
        log(DEBUG, 'Node %s already defined in Zabbix as host ID "%s"', node, hostid)
        params = zx.diff_node_host(node, host, log=log)

        if params:
            log(WARNING, 'Zabbix host ID "%s" configuration differs from current Node %s configuration', hostid, node)
            log(INFO, 'Updating Zabbix host ID "%s" according to Node %s with following parameters: %s',
                hostid, node, params)
            old_hostname = host['name']

            if zx.update_host(hostid, log=log, **params):
                log(INFO, 'Updated Zabbix host ID "%s"', hostid)
                zx.save_host_info(node, log=log)
                result = True
            else:
                log(ERROR, 'Could not update Zabbix host ID "%s"', hostid)
                result = False

            # Node hostname changed
            if 'name' in params:
                its = zx.update_node_service(old_hostname, name=params['name'])
                log(WARNING, 'Node %s hostname changed - updated Zabbix IT Service ID "%s"', node, its)

            return result

        # Host in sync with Node
        log(INFO, 'Zabbix host ID "%s" configuration is synchronized with current Node %s configuration', hostid, node)
        return True

    def node_status_sync(self, node, task_log=LOG):
        """[INTERNAL] Change host status in zabbix according to node status"""
        zx = self.izx
        log = zx.get_log_fun(task_log)
        hostid = zx.get_hostid(node, log=log)

        if not hostid:
            log(ERROR, 'Zabbix host for Node %s does not exist!', node)
            return False

        status = zx.node_host_status(node)
        status_display = node.get_status_display()

        log(WARNING, 'Setting Zabbix host ID "%s" status to %s for Node %s', hostid, status_display, node)

        if zx.update_host(hostid, log=log, status=status):
            log(INFO, 'Updated Zabbix host ID "%s" status to %s', hostid, status_display)
            zx.save_host_info(node, log=log)
            return True
        else:
            log(ERROR, 'Could not update Zabbix host ID "%s" status to %s', hostid, status_display)
            return False

    def node_delete(self, node, task_log=LOG):
        """[INTERNAL] Delete compute node zabbix host"""
        zx = self.izx
        log = zx.get_log_fun(task_log)
        node_uuid = zx.host_id(node)  # Node object does not exist at this point, it just carries the uuid
        host = zx.get_host(node_uuid, log=log)

        if not host:
            log(WARNING, 'Zabbix host for Node %s does not exist!', node_uuid)
            return False

        hostid = host['hostid']
        name = host['name']

        log(WARNING, 'Deleting Zabbix IT Service with name "%s" for Node %s', name, node_uuid)
        its = zx.delete_node_service(name)

        if its:
            log(INFO, 'Deleted Zabbix IT Service ID "%s" for Node %s', its, node_uuid)
        else:
            log(ERROR, 'Could not delete Zabbix IT Service with name "%s"', name)

        log(WARNING, 'Deleting Zabbix host ID "%s" for Node %s', hostid, node_uuid)

        if zx.delete_host(hostid, log=log):
            log(INFO, 'Deleted Zabbix host ID "%s"', hostid)
            result = True
        else:
            log(ERROR, 'Could not delete Zabbix host ID "%s"', hostid)
            result = False

        # Clear zabbix cache (node IT services are being cached and not needed)
        # Fix a situation when a compute node with the same name will be created again
        zx.reset_cache()

        return result

    def node_history(self, node_id, items, zhistory, since, until, items_search=None):
        """[INTERNAL] Return node history data for selected graph and period"""
        return self.izx.get_history(node_id, items, zhistory, since, until, items_search=items_search)
