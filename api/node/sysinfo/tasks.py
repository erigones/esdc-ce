from django.conf import settings

from api.utils.request import get_dummy_request
from api.task.utils import callback, mgmt_lock, task_log_success, task_log_error
from api.node.sysinfo.utils import parse_esysinfo
from api.node.messages import LOG_NODE_CREATE, LOG_NODE_UPDATE
from api.node.sshkey.tasks import run_node_authorized_keys_sync
from api.node.image.tasks import run_node_img_sources_sync
from api.vm.status.tasks import vm_status_all
from api.dns.record.api_views import RecordView
from vms.models import Node, DefaultDc
from vms.signals import node_created, node_json_changed
from que.tasks import cq, get_task_logger
from que.mgmt import MgmtCallbackTask
from que.exceptions import TaskException

__all__ = ('node_sysinfo_cb',)

logger = get_task_logger(__name__)


@cq.task(name='api.node.sysinfo.tasks.node_sysinfo_cb', base=MgmtCallbackTask, bind=True, ignore_result=False)
@mgmt_lock(wait_for_release=True, bound_task=True)
@callback(log_exception=True, update_user_tasks=True)
def node_sysinfo_cb(result, task_id, node_uuid=None):
    """
    A callback function for updating Node.json (sysinfo).

    node_uuid will be set only if called via API or GUI
    """
    # in case the callback is called by restarting erigonesd:fast service on compute node, the meta dict lacks
    # a lot of information; msg is required as part of exception logging inside callback decorator
    # therefore we set it explicitly
    result['meta']['msg'] = LOG_NODE_UPDATE

    if result['returncode'] != 0:
        logger.error('Found nonzero return code in result from esysinfo command on %s', node_uuid)
        raise TaskException(result, 'Got bad return code (%s)' % result['returncode'])

    stdout = result.pop('stdout', '')
    result.pop('stderr', None)
    node_new = False

    try:
        esysinfo = parse_esysinfo(stdout)
        img_sources = esysinfo.pop('img_sources')
        img_initial = esysinfo.pop('img_initial')
    except Exception as e:
        logger.error('Could not parse output from esysinfo command on %s. Error: %s', node_uuid, e)
        logger.exception(e)
        raise TaskException(result, 'Could not parse esysinfo output')
    else:
        uuid = esysinfo['sysinfo']['UUID']

    try:
        node = Node.objects.get(uuid=uuid)
    except Node.DoesNotExist:
        # The head node must be in online state during the admin DC initialization and each compute node must be in
        # online state during ssh key exchange.
        node_new = True
        is_head = not Node.objects.exists()
        logger.warn('Creating NEW node from sysinfo output from %s', node_uuid)
        node = Node.create_from_sysinfo(uuid, esysinfo, status=Node.ONLINE, is_head=is_head)
        node_created.send(task_id, node=node)  # Signal!
        result['message'] = 'Successfully created new compute node %s' % node.hostname
        task_log_success(task_id, msg=LOG_NODE_CREATE, obj=node, task_result=result,
                         update_user_tasks=True)
        sshkey_changed = bool(node.sshkey)

        if node.is_head:
            logger.warn('New node %s is the first node ever created - assuming head node status. '
                        'Initializing mgmt system and creating admin DC', node)
            from api.system.init import init_mgmt
            try:
                init_mgmt(node, images=img_initial)
            except Exception as e:
                logger.exception(e)
                result['message'] = 'Error while initializing admin datacenter (%s)' % e
                task_log_error(task_id, msg=LOG_NODE_CREATE, obj=node, task_result=result, update_user_tasks=True)

        logger.info('Saving node %s IP address "%s" into admin network', node, node.ip_address)
        try:  # We should proceed even if the IP address is not registered
            node.ip_address.save()
        except Exception as e:
            logger.exception(e)
        else:
            admin_net = node.ip_address.subnet  # The network was updated by init_mgmt()
            # Reload Subnet object because it is cached inside node instance
            admin_net = admin_net.__class__.objects.get(pk=admin_net.pk)
            # We need a request object
            request = get_dummy_request(DefaultDc(), 'POST', system_user=True)
            record_cls = RecordView.Record

            if admin_net.dns_domain and admin_net.dns_domain == node.domain_name:
                logger.info('Creating forward A DNS record for node %s', node)
                # This will fail silently
                RecordView.add_or_update_record(request, record_cls.A, admin_net.dns_domain, node.hostname,
                                                node.address, task_id=task_id, related_obj=node)

            if admin_net.ptr_domain:
                logger.info('Creating reverse PTR DNS record for node %s', node)
                # This will fail silently
                RecordView.add_or_update_record(request, record_cls.PTR, admin_net.ptr_domain,
                                                record_cls.get_reverse(node.address), node.hostname,
                                                task_id=task_id, related_obj=node)

    else:
        sshkey_changed = node.sshkey_changed(esysinfo)

        if node.sysinfo_changed(esysinfo) or sshkey_changed:
            logger.warn('Updating node %s json with sysinfo output from %s', node, node_uuid)
            node.update_from_sysinfo(esysinfo)  # Will save public SSH key too
            node_json_changed.send(task_id, node=node)  # Signal!
            result['message'] = 'Successfully updated compute node %s' % node.hostname
            task_log_success(task_id, msg=LOG_NODE_UPDATE, obj=node, task_result=result,
                             update_user_tasks=True)
        else:
            result['message'] = 'No changes detected on compute node %s' % node.hostname
            task_log_success(task_id, msg=LOG_NODE_UPDATE, obj=node, task_result=result,
                             update_user_tasks=True)

    if sshkey_changed:
        logger.warn('SSH key has changed on node %s - creating authorized_keys synchronization tasks', node)
        try:
            run_node_authorized_keys_sync()
        except Exception as e:
            logger.exception(e)

    try:
        run_node_img_sources_sync(node, img_sources)
    except Exception as e:
        logger.exception(e)

    if node_new:
        node.del_initializing()
        # Used by esdc-ee to change node status to unlicensed
        node_status = getattr(settings, 'VMS_NODE_STATUS_DEFAULT', None)

        if node_status:
            node.save_status(node_status)  # Set node status (most probably to unlicensed)
    else:
        # Always run vm_status_all for an old compute node
        vm_status_all(task_id, node)

    return result
