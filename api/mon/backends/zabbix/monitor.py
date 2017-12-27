from logging import INFO, WARNING, ERROR, DEBUG, getLogger

from api.decorators import catch_exception
from api.mon.backends.abstract import AbstractMonitoringBackend, LOG
from api.mon.backends.zabbix.containers import (ZabbixHostGroupContainer, ZabbixUserContainer, ZabbixUserGroupContainer,
                                                ZabbixActionContainer, ZabbixTemplateContainer)
from api.mon.backends.zabbix.base import ZabbixBase
from api.mon.backends.zabbix.internal import InternalZabbix
from api.mon.backends.zabbix.external import ExternalZabbix
from gui.models import User, AdminPermission
from vms.models import DefaultDc

logger = getLogger(__name__)

__ZABBIX__ = {}  # This hold an instance of zabbix per DC


def get_zabbix(dc, **kwargs):
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


def del_zabbix(dc):
    """
    Remove Zabbix instance from global cache.
    """
    global __ZABBIX__

    if dc.id in __ZABBIX__:
        del __ZABBIX__[dc.id]
        return True
    return False


class Zabbix(AbstractMonitoringBackend):
    """
    Public Zabbix class used via get_zabbix and del_zabbix functions.
    """
    zbx = ZabbixBase

    def __init__(self, dc, **kwargs):
        super(Zabbix, self).__init__(dc, **kwargs)

        # InternalZabbix need default DC, which can be the same as the dc parameter
        if dc.is_default():
            default_dc = dc
            reuse_zapi = True
        else:
            default_dc = DefaultDc()
            # Reuse zabbix connection if the server and username did not change
            dc_settings, dc1_settings = dc.settings, default_dc.settings
            reuse_zapi = (dc_settings.MON_ZABBIX_SERVER == dc1_settings.MON_ZABBIX_SERVER and
                          dc_settings.MON_ZABBIX_USERNAME == dc1_settings.MON_ZABBIX_USERNAME and
                          dc_settings.MON_ZABBIX_PASSWORD == dc1_settings.MON_ZABBIX_PASSWORD)

        self.izx = InternalZabbix(default_dc, **kwargs)
        self._connections = {self.izx.zapi}
        if reuse_zapi:
            kwargs['zapi'] = self.izx.zapi

        self.ezx = ExternalZabbix(dc, **kwargs)
        if not reuse_zapi:
            self._connections.add(self.ezx.zapi)

    def __hash__(self):
        return hash((self.izx, self.ezx))

    @property
    def enabled(self):
        """Same as dc.settings.MON_ZABBIX_ENABLED == True"""
        return self.izx.enabled and self.ezx.enabled

    @property
    def connected(self):
        """We are connected only if both zabbix objects are connected"""
        return self.izx.connected and self.ezx.connected

    def is_default_dc_connection_reused(self):
        """Are we using the same zabbix connection for internal and external zabbix server?
        We assume that the internal Zabbix server is always the same as in the default DC"""
        return len(self._connections) == 1

    def reset_cache(self):
        """Clear cache for both zabbix objects"""
        self.izx.reset_cache()
        self.ezx.reset_cache()

    @catch_exception
    def task_log_success(self, task_id, obj=None, msg='', detail='', **kwargs):
        from api.task.utils import task_log_success

        if obj is None:
            obj = self.server_class(self.dc)

        task_log_success(task_id, msg, obj=obj, detail=detail, **kwargs)

    @catch_exception
    def task_log_error(self, task_id, obj=None, msg='', detail='', **kwargs):
        from api.task.utils import task_log_error

        if obj is None:
            obj = self.server_class(self.dc)

        task_log_error(task_id, msg, obj=obj, detail=detail, **kwargs)

    @classmethod
    @catch_exception
    def vm_send_alert(cls, vm, msg, priority=ZabbixBase.HIGH, **kwargs):
        """[INTERNAL] Convenient shortcut for sending VM related alerts"""
        dc = vm.dc
        dcs = dc.settings

        if not (dcs.MON_ZABBIX_ENABLED and vm.is_zabbix_sync_active()):
            logger.warning('Not sending alert for VM %s, because it has monitoring disabled', vm)
            return

        if vm.is_notcreated():
            logger.warning('Not sending alert for VM %s, because it is not created', vm)
            return

        izx = get_zabbix(dc).izx  # InternalZabbix from cache

        return izx.send_alert(izx.host_id(vm), msg, priority=priority, **kwargs)

    @classmethod
    @catch_exception
    def node_send_alert(cls, node, msg, priority=ZabbixBase.HIGH, **kwargs):
        """[INTERNAL] Convenient shortcut for sending Node related alerts"""
        dc = DefaultDc()
        dcs = dc.settings

        if not (dcs.MON_ZABBIX_ENABLED and dcs.MON_ZABBIX_NODE_SYNC):  # dc1_settings
            logger.warning('Not sending alert for Node %s, because global node monitoring disabled', node)
            return

        if node.is_online():
            logger.warning('Not sending alert for Node %s, because it is not online', node)
            return

        izx = get_zabbix(dc).izx

        return izx.send_alert(izx.host_id(node), msg, priority=priority, **kwargs)

    def vm_sla(self, vm_node_history):
        """[INTERNAL] Return SLA (%) for VM.node_history and selected time period; Returns None in case of problems"""
        return self.izx.vm_get_sla(vm_node_history)

    def vm_history(self, vm_host_id, items, zhistory, since, until, items_search=None):
        """[INTERNAL] Return VM history data for selected graph and period"""
        return self.izx.get_history((vm_host_id,), items, zhistory, since, until, items_search=items_search)

    def vms_history(self, vm_host_ids, items, zhistory, since, until, items_search=None):
        """[INTERNAL] Return VM history data for selected VMs, graph and period"""
        return self.izx.get_history(vm_host_ids, items, zhistory, since, until, items_search=items_search)

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
        return self.izx.get_history((node_id,), items, zhistory, since, until, items_search=items_search)

    def template_list(self, full=False, extended=False):
        """[EXTERNAL] Return list of available templates"""
        if full or extended:
            display_attr = 'as_mgmt_data'
        else:
            display_attr = 'name'

        return [getattr(ztc, display_attr) for ztc in ZabbixTemplateContainer.all(self.ezx.zapi)]

    def hostgroup_list(self, dc_name=None, full=False, extended=False):
        """[EXTERNAL] Return list of available hostgroups"""
        if full or extended:
            display_attr = 'as_mgmt_data'
        else:
            display_attr = 'name_without_dc_prefix'

        return [getattr(zgc, display_attr) for zgc in ZabbixHostGroupContainer.all(self.ezx.zapi, dc_name=dc_name)]

    def hostgroup_detail(self, name):
        """[EXTERNAL]"""
        zbx_name = ZabbixHostGroupContainer.hostgroup_name_factory(self.dc.name, name)
        zgc = ZabbixHostGroupContainer.from_zabbix_name(self.ezx.zapi, zbx_name)

        return zgc.as_mgmt_data

    def hostgroup_create(self, name):
        """[EXTERNAL]"""
        zbx_name = ZabbixHostGroupContainer.hostgroup_name_factory(self.dc.name, name)
        zgc = ZabbixHostGroupContainer.from_mgmt_data(self.ezx.zapi, zbx_name)
        zgc.create()

        return zgc.as_mgmt_data

    def hostgroup_delete(self, name):
        """[EXTERNAL]"""
        zbx_name = ZabbixHostGroupContainer.hostgroup_name_factory(self.dc.name, name)
        zgc = ZabbixHostGroupContainer.from_zabbix_name(self.ezx.zapi, zbx_name)
        zgc.delete()

        return None

    def _get_filtered_alerts(self, vms=None, nodes=None, **kwargs):
        """This is a generator function"""
        if vms is None and nodes is None:
            host_ids = None
        else:
            vm_host_ids = (ExternalZabbix.get_cached_hostid(vm) for vm in vms or ())
            node_host_ids = (InternalZabbix.get_cached_hostid(node) for node in nodes or ())
            host_ids = [hostid for hostid in vm_host_ids if hostid] + [hostid for hostid in node_host_ids if hostid]

        return self.ezx.show_alerts(hostids=host_ids, **kwargs)

    def alert_list(self, *args, **kwargs):
        """[EXTERNAL] Return list of available alerts"""
        return list(self._get_filtered_alerts(*args, **kwargs))

    def user_group_sync(self, group=None, dc_as_group=None):
        """[EXTERNAL]"""
        kwargs = {}
        # TODO create also a separate superadmin group for superadmins in every DC

        if dc_as_group:
            # special case when DC itself acts as a group
            kwargs['superusers'] = True
            kwargs['group_name'] = ZabbixUserGroupContainer.user_group_name_factory(
                dc_name=self.dc.name, local_group_name=ZabbixUserGroupContainer.OWNERS_GROUP
            )
            kwargs['users'] = [User.objects.filter(dc=self.dc).first()]  # cannot use self.dc.owner due to cache !!!
            kwargs['accessible_hostgroups'] = ()  # TODO
        else:
            kwargs['group_name'] = ZabbixUserGroupContainer.user_group_name_factory(dc_name=self.dc.name,
                                                                                    local_group_name=group.name)
            kwargs['users'] = group.user_set.all()
            kwargs['accessible_hostgroups'] = ()  # TODO
            kwargs['superusers'] = group.permissions.filter(name=AdminPermission.name).exists()

        return ZabbixUserGroupContainer.synchronize(self.ezx.zapi, **kwargs)

    def user_sync(self, user):
        """[EXTERNAL]"""
        return ZabbixUserContainer.synchronize(self.ezx.zapi, user)

    def user_group_delete(self, name):
        """[EXTERNAL]"""
        group_name = ZabbixUserGroupContainer.user_group_name_factory(dc_name=self.dc.name, local_group_name=name)

        return ZabbixUserGroupContainer.delete_by_name(self.ezx.zapi, group_name)

    def user_delete(self, name):
        """[EXTERNAL]"""
        return ZabbixUserContainer.delete_by_name(self.ezx.zapi, name)

    def action_list(self, full=False, extended=False):
        """[EXTERNAL]"""
        if full or extended:
            display_attr = 'as_mgmt_data'
        else:
            display_attr = 'name_without_dc_prefix'

        return [getattr(zac, display_attr) for zac in ZabbixActionContainer.all(self.ezx.zapi, self.dc.name)]

    def action_detail(self, name):
        """[EXTERNAL]"""
        zbx_name = ZabbixActionContainer.user_group_name_factory(self.dc.name, name)
        zac = ZabbixActionContainer.from_zabbix_name(self.ezx.zapi, zbx_name)

        return zac.as_mgmt_data

    def action_create(self, name, data):
        """[EXTERNAL]"""
        zbx_name = ZabbixActionContainer.user_group_name_factory(self.dc.name, name)
        zac = ZabbixActionContainer.from_mgmt_data(self.ezx.zapi, zbx_name)
        zac.create(self.dc.name, data)

        return zac.as_mgmt_data

    def action_update(self, name, data):
        """[EXTERNAL]"""
        data.pop('name', None)  # Action name cannot be changed
        zbx_name = ZabbixActionContainer.user_group_name_factory(self.dc.name, name)
        zac = ZabbixActionContainer.from_zabbix_name(self.ezx.zapi, zbx_name,
                                                     # we don't need to fetch hostgroups when we are replacing them
                                                     resolve_hostgroups='hostgroups' not in data,
                                                     # we don't need to fetch usergroups when we are replacing them
                                                     resolve_usergroups='usergroups' not in data)
        zac.update(self.dc.name, data)

        return zac.as_mgmt_data

    def action_delete(self, name):
        """[EXTERNAL]"""
        zbx_name = ZabbixActionContainer.user_group_name_factory(self.dc.name, name)
        zac = ZabbixActionContainer.from_zabbix_name(self.ezx.zapi, zbx_name)
        zac.delete()

        return None
