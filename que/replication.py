from __future__ import absolute_import

from que import Q_MGMT
from que.erigonesd import cq
from que.utils import generate_internal_task_id
from que.exceptions import CallbackError

ERIGONES_TASK_USER = cq.conf.ERIGONES_TASK_USER
ESREP_SYNC_CB = 'api.vm.replica.tasks.vm_replica_sync_cb'


def esrep_sync_cb(result, task_prefix):
    """
    esrep sync callback -> send to api.vm.replica.tasks.vm_replica_sync_cb @ mgmt.
    """
    result['task_prefix'] = task_prefix
    task_id = generate_internal_task_id()
    task = cq.send_task(ESREP_SYNC_CB, args=(result, task_id), queue=Q_MGMT, expires=120, task_id=task_id)

    if not task:
        raise CallbackError('Failed to created task "%s"' % ESREP_SYNC_CB)

    return task
