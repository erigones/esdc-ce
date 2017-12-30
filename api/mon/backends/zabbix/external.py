from logging import WARNING, INFO

from django.core.cache import cache

from api.mon.backends.zabbix.base import ZabbixBase


class ExternalZabbix(ZabbixBase):
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

        return self._get_or_create_hostgroups(self._vm_kwargs(vm),
                                              self.settings.MON_ZABBIX_HOSTGROUP_VM,
                                              vm.dc.name,
                                              hostgroups,
                                              log)

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
        return self._create_host(vm, self._vm_host_interface(vm),
                                 groups=self._vm_groups(vm, log=log),
                                 templates=self._vm_templates(vm, log=log))

    def diff_vm_host(self, vm, host, log=None):
        """Compare VM (DB) and host (Zabbix) configuration and create an update dict"""
        return self._diff_host(vm, host, self._vm_host_interface(vm),
                               groups=self._vm_groups(vm, log=log),
                               templates=self._vm_templates(vm, log=log),
                               proxy_id=self._vm_proxy_id(vm))
