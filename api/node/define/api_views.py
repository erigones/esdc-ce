from logging import getLogger

from django.db.models.signals import post_delete
from django.core.exceptions import ObjectDoesNotExist

from vms.models import Node, Vm
from api.api_views import APIView
from api.exceptions import NodeHasPendingTasks
from api.decorators import catch_exception
from api.serializers import ForceSerializer
from api.signals import node_status_changed, node_online, node_offline, node_deleted, vm_undefined
from api.task.utils import TaskID
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.node.define.serializers import NodeDefineSerializer
from api.node.messages import LOG_DEF_UPDATE, LOG_DEF_DELETE
from api.dns.record.api_views import RecordView
from api.mon.node.tasks import node_json_changed

logger = getLogger(__name__)


class NodeDefineView(APIView):
    dc_bound = False
    order_by_default = order_by_fields = ('hostname',)

    def __init__(self, request, node, **kwargs):
        super(NodeDefineView, self).__init__(request, **kwargs)
        self.node = node

    @catch_exception
    def _delete_ip_address(self, ip_address):
        if ip_address.usage == ip_address.NODE:
            logger.info('Deleting IP address %s associated with node %s', ip_address, self.node)
            ip_address.delete()

    @catch_exception
    def _create_ip_address(self):
        try:
            ip_address = self.node.create_ip_address()
        except ObjectDoesNotExist:
            return None

        logger.info('Creating IP address %s associated with node %s', ip_address, self.node)
        ip_address.save()

        return ip_address

    @catch_exception
    def _delete_dns_records(self, task_id, node, hostname, ip_address):
        admin_net = ip_address.subnet
        record_cls = RecordView.Record

        if admin_net.dns_domain:
            logger.info('Deleting forward A DNS record for node %s', hostname)
            RecordView.delete_record(self.request, record_cls.A, admin_net.dns_domain, hostname,
                                     task_id=task_id, related_obj=node)

        if admin_net.ptr_domain:
            logger.info('Deleting reverse PTR DNS record for node %s', hostname)
            RecordView.delete_record(self.request, record_cls.PTR, admin_net.ptr_domain,
                                     record_cls.get_reverse(ip_address.ip), task_id=task_id, related_obj=node)

    @catch_exception
    def _add_or_update_dns_records(self, task_id, ip_address):
        hostname = self.node.hostname
        admin_net = ip_address.subnet
        record_cls = RecordView.Record

        if admin_net.dns_domain:
            logger.info('Adding or updating forward A DNS record for node %s', hostname)
            RecordView.add_or_update_record(self.request, record_cls.A, admin_net.dns_domain, hostname,
                                            task_id=task_id, related_obj=self.node)

        if admin_net.ptr_domain:
            logger.info('Adding or updating reverse PTR DNS record for node %s', hostname)
            RecordView.add_or_update_record(self.request, record_cls.PTR, admin_net.ptr_domain,
                                            record_cls.get_reverse(ip_address.ip),
                                            task_id=task_id, related_obj=self.node)

    @staticmethod
    def _delete_queue(channel, queue, fail_silently=False):
        """Delete amqp queue named after node hostname"""
        try:
            count = channel.queue_delete(queue)
        except Exception as exc:
            if fail_silently:
                logger.warn('Could not delete queue "%s". Error was: %s', queue, exc)
            else:
                raise exc
        else:
            logger.info('Queue "%s" was successfully deleted along with %s tasks', queue, count)
            return count

    @classmethod
    @catch_exception
    def _delete_queues(cls, queues, fail_silently=False):
        """Delete all amqp queues"""
        from que.erigonesd import cq

        with cq.connection() as conn:
            for queue in queues:
                cls._delete_queue(conn.default_channel, queue, fail_silently=fail_silently)

    def get(self, many=False):
        """Get node definition(s)"""
        node = self.node

        if many:
            if node:
                res = NodeDefineSerializer(self.request, node, many=True).data
            else:
                res = []
        else:
            res = NodeDefineSerializer(self.request, node).data

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    def _post_update(self, task_id, ser):
        """Called after put() saves updated node properties"""
        if ser.address_changed:
            if ser.old_ip_address:
                # Delete DNS records associated with node; fail silently
                self._delete_dns_records(task_id, self.node, self.node.hostname, ser.old_ip_address)
                # Delete IP address associated with node; fail silently
                self._delete_ip_address(ser.old_ip_address)

            # Create IP address object associated with node; fail silently
            ip_address = self._create_ip_address()

            if ip_address:
                # Create DNS records associated with node; fail silently
                self._add_or_update_dns_records(task_id, ip_address)

    def put(self):
        """Update node definition"""
        node = self.node
        ser = NodeDefineSerializer(self.request, node, data=self.data, partial=True)

        if node.tasks:
            raise NodeHasPendingTasks

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=node, dc_bound=False)

        if ser.status_changed == Node.OFFLINE and node.has_related_tasks():
            raise NodeHasPendingTasks('Node has related objects with pending tasks')

        # Changing cpu or disk coefficients can lead to negative numbers in node.cpu/ram_free or dc_node.cpu/ram_free;
        # This is solved by running the DB update inside a transaction and checking for negative values (=> rollback)
        errors = ser.save()

        if errors:
            return FailureTaskResponse(self.request, errors, obj=node, dc_bound=False)

        res = SuccessTaskResponse(self.request, ser.data, obj=node, detail_dict=ser.detail_dict(), dc_bound=False,
                                  msg=LOG_DEF_UPDATE)
        task_id = TaskID(res.data.get('task_id'), request=self.request)

        # Delete obsolete IP address and DNS records and create new ones if possible
        self._post_update(task_id, ser)

        # Signals section (should go last)
        if ser.status_changed:
            node_status_changed.send(task_id, node=node, automatic=False)  # Signal!

            if node.is_online():
                node_online.send(task_id, node=node, automatic=False)  # Signal!
            elif node.is_offline():
                node_offline.send(task_id, node=node)  # Signal!

        if ser.monitoring_changed or ser.address_changed:
            node_json_changed.send(task_id, node=node)  # Signal!

        return res

    def _post_delete(self, task_id, node, hostname, ip_address, queues):
        """The parameter are passed directly because the node may not exist anymore"""
        if ip_address:
            # Delete DNS records associated with node; fail silently
            self._delete_dns_records(task_id, node, hostname, ip_address)
            # Delete IP address associated with node; fail silently
            self._delete_ip_address(ip_address)

        # Delete celery (amqp) task queues (named after node hostname); fail silently
        self._delete_queues(queues, fail_silently=True)

    def delete(self):
        """Delete node definition"""
        node = self.node

        force = bool(ForceSerializer(data=self.data, default=False))

        # Check if node has VMs and backups if not using force
        if force:
            # Fetch data for vm_undefined signal
            vms = [{'vm_uuid': vm.uuid, 'dc': vm.dc, 'zabbix_sync': vm.is_zabbix_sync_active(),
                    'external_zabbix_sync': vm.is_external_zabbix_sync_active()}
                   for vm in node.vm_set.select_related('dc').all()]
        else:
            vms = ()
            # Simulate turning compute and backup flags off
            ser = NodeDefineSerializer(self.request, node, data={'is_backup': False, 'is_compute': False}, partial=True)

            if not ser.is_valid():
                return FailureTaskResponse(self.request, ser.errors, obj=node, dc_bound=False)

        if node.tasks:
            raise NodeHasPendingTasks

        if node.has_related_tasks():
            raise NodeHasPendingTasks('Node has related objects with pending tasks')

        uuid = node.uuid
        hostname = node.hostname
        obj = node.log_list
        owner = node.owner
        queues = node.all_queues

        try:
            ip_address = node.ip_address
        except ObjectDoesNotExist:
            ip_address = None

        # Bypass signal handling for VMs (needed when using force)
        #   Fixes: IntegrityError: insert or update on table "vms_nodestorage"
        post_delete.disconnect(Vm.post_delete, sender=Vm, dispatch_uid='post_delete_vm')

        try:
            node.delete()
        finally:
            post_delete.connect(Vm.post_delete, sender=Vm, dispatch_uid='post_delete_vm')

        res = SuccessTaskResponse(self.request, None, obj=obj, owner=owner, detail_dict={'force': force},
                                  msg=LOG_DEF_DELETE, dc_bound=False)
        task_id = TaskID(res.data.get('task_id'), request=self.request)

        # Force deletion will delete all node related objects (VMs, backups...)
        for vm in vms:
            try:
                vm_undefined.send(task_id, **vm)  # Signal! for every vm on deleted node
            except Exception as exc:
                logger.exception(exc)

        # Post delete cleanup (IP address, DNS records, message queues)
        self._post_delete(task_id, node, hostname, ip_address, queues)

        # Signals should be called last
        node_deleted.send(task_id, node_uuid=uuid, node_hostname=hostname)  # Signal!

        return res
