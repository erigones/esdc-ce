from que.tasks import cq, get_task_logger
from que.mgmt import MgmtCallbackTask
from que.utils import dc_id_from_task_id
from que.exceptions import TaskException
from api.utils.request import get_dummy_request
from api.utils.views import call_api_view
from api.task.utils import callback
from api.task.tasks import task_log_cb_success, task_log_cb_error
from api.node.vm.utils import vm_from_json
from vms.models import Dc, Node, Vm
from vms.utils import PickleDict
from vms.signals import vm_deployed

__all__ = ('harvest_vm_cb',)

logger = get_task_logger(__name__)


def _vm_update(vm):
    logger.info('Running PUT vm_manage(%s)', vm)
    from api.vm.base.views import vm_manage
    request = get_dummy_request(vm.dc, method='PUT', system_user=True)
    res = call_api_view(request, 'PUT', vm_manage, vm.hostname)

    if res.status_code == 201:
        logger.info('PUT vm_manage(%s) was successful: %s', vm, res.data)
    else:
        logger.error('PUT vm_manage(%s) failed: %s (%s): %s', vm, res.status_code, res.status_text, res.data)


@cq.task(name='api.node.vm.tasks.harvest_vm_cb', base=MgmtCallbackTask, bind=True)
@callback()
def harvest_vm_cb(result, task_id, node_uuid=None):
    node = Node.objects.get(uuid=node_uuid)
    dc = Dc.objects.get_by_id(dc_id_from_task_id(task_id))
    err = result.pop('stderr', None)
    vms = []
    vms_err = []
    jsons = []

    if result.pop('returncode', None) != 0 or err:
        logger.error('Found nonzero returncode in result from harvest_vm(%s). Error: %s', node, err)
        raise TaskException(result, 'Got bad return code (%s). Error: %s' % (result['returncode'], err))

    for json in result.pop('stdout', '').split('||||'):
        json = json.strip()
        if json:
            try:
                jsons.append(PickleDict.load(json))
            except Exception as e:
                logger.error('Could not parse json output from harvest_vm(%s). Error: %s', node, e)
                raise TaskException(result, 'Could not parse json output')

    if not jsons:
        raise TaskException(result, 'Missing json output')

    request = get_dummy_request(dc, method='POST', system_user=True)

    for json in jsons:
        vm_uuid = json.get('uuid', None)  # Bad uuid will be stopped later in vm_from_json()
        if vm_uuid:
            if Vm.objects.filter(uuid=vm_uuid).exists():
                logger.warning('Ignoring VM %s found in harvest_vm(%s)', vm_uuid, node)
                continue
        try:
            vm = vm_from_json(request, task_id, json, dc, template=True, save=True,
                              update_ips=True, update_dns=True)
        except Exception as e:
            logger.exception(e)
            logger.error('Could not load VM from json:\n"""%s"""', json)
            err_msg = 'Could not load server %s. Error: %s' % (vm_uuid, e)
            task_log_cb_error({'message': err_msg}, task_id, obj=node, **result['meta'])
            vms_err.append(vm_uuid)
        else:
            logger.info('Successfully saved new VM %s after harvest_vm(%s)', vm, node)
            vms.append(vm.hostname)
            vm_deployed.send(task_id, vm=vm)  # Signal!  (will update monitoring)

            if vm.json_changed():
                try:
                    _vm_update(vm)
                except Exception as e:
                    logger.exception(e)

    if vms or not vms_err:
        if vms:
            result['message'] = 'Successfully harvested %s server(s) (%s)' % (len(vms), ','.join(vms))
        else:
            result['message'] = 'No new server found'

        task_log_cb_success(result, task_id, obj=node, **result['meta'])
        return result
    else:
        raise TaskException(result, 'Could not find or load any server')
