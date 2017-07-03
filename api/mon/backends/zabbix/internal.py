from logging import ERROR, WARNING, INFO

from django.conf import settings as django_settings
from zabbix_api import ZabbixAPIException

from api.decorators import catch_exception
from .base import ZabbixError, ZabbixBase, logger


class InternalZabbix(ZabbixBase):
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
            '{$ZONEID}': '-',  # Issue #129
            '{$UUID_SHORT}': vm.uuid[:30],
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

    def send_alert(self, host, msg, priority=ZabbixBase.NOT_CLASSIFIED, include_signature=True):
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
