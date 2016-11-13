from logging import getLogger

from django.utils.translation import ugettext_noop as _
from django.utils.six import iteritems
from django.db.transaction import atomic

from vms.models import Node
from api import status as scode
from api.api_views import APIView
from api.exceptions import VmIsNotOperational, ExpectationFailed, VmHasPendingTasks
from api.utils.request import set_request_method
from api.task.utils import TaskID
from api.task.response import SuccessTaskResponse, FailureTaskResponse, to_string
from api.signals import vm_defined, vm_undefined
from api.mon.vm.tasks import vm_json_active_changed
from api.vm.base.utils import vm_update_ipaddress_usage
from api.vm.define.utils import is_vm_operational
from api.vm.define.api_views import VmDefineBaseView
from api.vm.define.vm_define_nic import VmDefineNicView
from api.vm.define.vm_define_disk import VmDefineDiskView
from api.vm.define.events import VmDefineHostnameChanged
from api.vm.define.serializers import VmDefineSerializer, VmDefineDiskSerializer, VmDefineNicSerializer
from api.vm.messages import LOG_DEF_CREATE, LOG_DEF_UPDATE, LOG_DEF_DELETE, LOG_DEF_REVERT

logger = getLogger(__name__)


class VmDefineView(VmDefineBaseView):
    order_by_default = order_by_fields = ('hostname',)

    def _node(self, vm):
        """Return dict with VM node hostname and color"""
        if not vm.node:
            return None

        res = {'color': vm.node.color}
        if self.request.user.is_admin(self.request):
            res['hostname'] = vm.node.hostname

        return res

    def _get_vm_define(self, vm):
        """Get one VM definition"""
        if self.active:
            vm.revert_active()

        res = VmDefineSerializer(self.request, vm).data

        if self.full:
            res['disks'] = VmDefineDiskSerializer(self.request, vm, vm.json_get_disks(), many=True).data
            res['nics'] = VmDefineNicSerializer(self.request, vm, vm.json_get_nics(), many=True).data

        return res

    def get_diff(self, vm, full=False):
        """Show differences between active and in db json vm_define."""
        def_current = VmDefineSerializer(self.request, vm).data

        if full:
            res = {
                'disks': VmDefineDiskView(self.request).get_diff(vm),
                'nics': VmDefineNicView(self.request).get_diff(vm),
            }
        else:
            res = {}

        vm.revert_active()
        def_active = VmDefineSerializer(self.request, vm).data
        vm_diff = self._diff_dicts(def_active, def_current)

        if vm_diff.get('change', False):
            res.update(vm_diff)

        return res

    def _create_disks_and_nics(self, vm):
        """Try to create disks and nics defined by template"""
        # WARNING: This will temporary change the request.method to POST
        old_method = self.request.method
        request = set_request_method(self.request, 'POST')

        try:
            if not vm.json_get_disks():
                vm_define_disk = VmDefineDiskView(request)
                for i, data in enumerate(vm.template.vm_define_disk):
                    if data:
                        if i == 0 and not vm.is_kvm():  # Non-global zone's 1st disk can be only modified
                            logger.info('Updating disk_id=%d for vm %s defined by template %s', i, vm, vm.template)
                            res = vm_define_disk.put(vm, i, data)
                            if res.status_code != scode.HTTP_200_OK:
                                logger.warn('Failed (%s) to modify disk_id=%s in vm %s defined by template %s. '
                                            'Error: %s', res.status_code, i, vm, vm.template, res.data)
                        else:
                            logger.info('Creating disk_id=%d for vm %s defined by template %s', i, vm, vm.template)
                            res = vm_define_disk.post(vm, i, data)
                            if res.status_code != scode.HTTP_201_CREATED:
                                logger.warn('Failed (%s) to add disk_id=%s into vm %s defined by template %s. '
                                            'Error: %s', res.status_code, i, vm, vm.template, res.data)
                                break

            if not vm.json_get_nics():
                vm_define_nic = VmDefineNicView(request)
                for i, data in enumerate(vm.template.vm_define_nic):
                    if data:
                        logger.info('Creating nic_id=%d for vm %s defined by template %s', i, vm, vm.template)
                        res = vm_define_nic.post(vm, i, data)
                        if res.status_code != scode.HTTP_201_CREATED:
                            logger.warn('Failed (%s) to add nic_id=%s into vm %s defined by template %s. '
                                        'Error: %s', res.status_code, i, vm, vm.template, res.data)
                            break
        finally:
            set_request_method(request, old_method)

    # noinspection PyUnusedLocal
    def get(self, vm, data, many=False, **kwargs):
        """Get VM definition"""
        if (data and data.get('node', False)) or self.request.query_params.get('node', False):
            # Used in gsio.js for getting node hostname after VM deploy process is started
            return SuccessTaskResponse(self.request, {'node': self._node(vm)})

        if many:
            res = [self._get_vm_define(i) for i in vm]
        else:
            if self.diff:
                res = self.get_diff(vm, full=self.full)
            else:
                res = self._get_vm_define(vm)

        return SuccessTaskResponse(self.request, res)

    # noinspection PyUnusedLocal
    @atomic
    def post(self, vm, data, hostname=None):
        """Create VM definition"""
        ser = VmDefineSerializer(self.request, data=data, hostname=hostname)

        if ser.is_valid():
            ser.object.save(sync_json=True, update_node_resources=ser.update_node_resources)
            vm = ser.object

            try:
                res = SuccessTaskResponse(self.request, ser.data, status=scode.HTTP_201_CREATED, vm=vm,
                                          msg=LOG_DEF_CREATE, detail_dict=ser.detail_dict())
                vm_defined.send(TaskID(res.data.get('task_id'), request=self.request), vm=vm)  # Signal!

                return res
            finally:
                # Create disk/nics if defined in template
                if vm.template:
                    self._create_disks_and_nics(vm)

        return FailureTaskResponse(self.request, ser.errors)

    # noinspection PyUnusedLocal
    @is_vm_operational
    @atomic
    def put(self, vm, data, task_id=None, **kwargs):
        """Common code for updating VM properties used in vm_define and gui.vm.forms.ServerSettingsForm"""
        ser = VmDefineSerializer(self.request, vm, data=data, partial=True)

        if ser.is_valid():
            ser.object.save(sync_json=True,
                            update_hostname=ser.hostname_changed,
                            update_node_resources=ser.update_node_resources,
                            update_storage_resources=ser.update_storage_resources)

            if ser.hostname_changed:
                # Task event for GUI
                VmDefineHostnameChanged(self.request, vm, ser.old_hostname).send()

            try:
                return SuccessTaskResponse(self.request, ser.data, vm=vm, task_id=task_id,
                                           msg=LOG_DEF_UPDATE, detail_dict=ser.detail_dict())
            finally:
                if ser.template_changed:
                    self._create_disks_and_nics(vm)

        return FailureTaskResponse(self.request, ser.errors, vm=vm, task_id=task_id)

    # noinspection PyUnusedLocal
    @is_vm_operational
    @atomic
    def delete(self, vm, data, **kwargs):
        """Delete VM definition"""
        if vm.is_deployed():
            raise VmIsNotOperational(_('VM is not notcreated'))

        # noinspection PyUnusedLocal
        ser = VmDefineSerializer(self.request, vm)
        owner = vm.owner
        dead_vm = vm.log_list
        uuid = vm.uuid
        hostname = vm.hostname
        alias = vm.alias
        zabbix_sync = vm.is_zabbix_sync_active()
        external_zabbix_sync = vm.is_external_zabbix_sync_active()
        task_id = SuccessTaskResponse.gen_task_id(self.request, vm=dead_vm, owner=owner)

        # Every VM NIC could have an association to other tables. Cleanup first:
        for nic in vm.json_get_nics():
            # noinspection PyBroadException
            try:
                nic_ser = VmDefineNicSerializer(self.request, vm, nic)
                nic_ser.delete_ip(task_id)
            except Exception as ex:
                logger.exception(ex)
                continue

        # Finally delete VM
        logger.debug('Deleting VM %s from DB', vm)
        vm.delete()

        try:
            return SuccessTaskResponse(self.request, None, vm=dead_vm, owner=owner, task_id=task_id, msg=LOG_DEF_DELETE)
        finally:
            # Signal!
            vm_undefined.send(TaskID(task_id, request=self.request), vm_uuid=uuid, vm_hostname=hostname, vm_alias=alias,
                              dc=self.request.dc, zabbix_sync=zabbix_sync, external_zabbix_sync=external_zabbix_sync)

    def choose_node(self, vm):
        """Used by POST vm_manage when node needs to be chosen automatically"""
        new_node = Node.choose(vm)
        err = 'Could not find node with free resources'

        if not new_node:
            raise ExpectationFailed(err)

        old_method = self.request.method
        request = set_request_method(self.request, 'PUT')
        res = self.put(vm, {'node': new_node.hostname})
        set_request_method(request, old_method)

        if res.status_code != scode.HTTP_200_OK:
            try:
                err = res.data['result']['node']
            except Exception as e:
                logger.exception(e)
            raise ExpectationFailed(err)

        return new_node


class VmDefineRevertView(APIView):
    """
    Revert vm definition to json_active (undo).
    """
    @staticmethod
    def nice_diff(vm_diff):
        """Return ascii-readable VM diff"""
        res = []
        change = []
        add = []
        remove = []
        disks = vm_diff.get('disks', {})
        nics = vm_diff.get('nics', {})

        def __get_changes(items):
            return ['%s=%s->%s' % (key, to_string(val[0]), to_string(val[1])) for key, val in iteritems(items)]

        def __disk_nics_changes(items, id_name, id_value):
            return '%s=%s: ' % (id_name, id_value) + ', '.join(__get_changes(items))

        def __disk_nics_add_rem(items, id_name, id_value):
            add_rem = ['%s=%s' % (key, to_string(val)) for key, val in iteritems(items) if key != id_name]
            return '%s=%s: ' % (id_name, id_value) + ', '.join(add_rem)

        change_vm_define = __get_changes(vm_diff.get('change', {}))

        if change_vm_define:
            change.append(', '.join(change_vm_define))

        for xid, stuff in iteritems(disks.get('change', {})):
            change.append(__disk_nics_changes(stuff, 'disk_id', xid))

        for xid, stuff in iteritems(nics.get('change', {})):
            change.append(__disk_nics_changes(stuff, 'nic_id', xid))

        for action, store in (('add', add), ('remove', remove)):
            for idname, nics_or_disks in (('nic_id', nics), ('disk_id', disks)):
                for xid, stuff in iteritems(nics_or_disks.get(action, {})):
                    store.append(__disk_nics_add_rem(stuff, idname, xid))

        for i, j in (('change', change), ('add', add), ('remove', remove)):
            if j:
                res.append('* %s:' % i)
                res.extend('** %s' % k for k in j)

        return '\n'.join(res)

    # noinspection PyUnusedLocal
    @is_vm_operational
    @atomic
    def put(self, vm, data):
        """Revert json_active (undo). Problematic attributes:
            - hostname  - handled by revert_active() + change requires some post configuration
            - alias     - handled by revert_active()
            - owner     - handled by revert_active()
            - template  - handled by revert_active()
            - monitored - handled by revert_active(), but mon_vm_sync task must be run via vm_json_active_changed signal
            - tags      - wont be reverted (not saved in json)
            - nics.*.ip - ip reservation is fixed via vm_update_ipaddress_usage()
            - nics.*.dns + ptr - known bug - wont be reverted
        """
        if vm.is_notcreated():
            raise VmIsNotOperational('VM is not created')

        if vm.json == vm.json_active:
            raise ExpectationFailed('VM definition unchanged')

        if vm.tasks:
            raise VmHasPendingTasks

        # Prerequisites
        vm.hostname_is_valid_fqdn(cache=False)  # Cache vm._fqdn hostname/domain pair and find dns record
        hostname = vm.hostname  # Save hostname configured in DB

        # The magic happens here: get_diff() will run vm.revert_active() and return a diff
        vm_diff = VmDefineView(self.request).get_diff(vm, full=True)

        # Save VM
        hostname_changed = hostname != vm.hostname
        vm.unlock()  # vm saving was locked by revert_active()
        vm.save(update_hostname=hostname_changed, update_node_resources=True, update_storage_resources=True)

        # Generate response
        detail = 'Reverted VM configuration from %s.\n%s' % (vm.changed.strftime('%Y-%m-%d %H:%M:%S%z'),
                                                             self.nice_diff(vm_diff))
        vm_diff['reverted_from'] = vm.changed

        res = SuccessTaskResponse(self.request, vm_diff, detail=detail, msg=LOG_DEF_REVERT, vm=vm)

        # Post-save stuff
        task_id = TaskID(res.data.get('task_id'), request=self.request)
        vm_update_ipaddress_usage(vm)
        vm_json_active_changed.send(task_id, vm=vm)  # Signal!

        if hostname_changed:
            VmDefineHostnameChanged(self.request, vm, hostname).send()  # Task event for GUI

        return res
