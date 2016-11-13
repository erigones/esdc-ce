from que.tasks import execute_sysinfo
from que.utils import user_owner_ids_from_task_id


def node_startup(task_id, node=None, **kwargs):
    """
    Create esysinfo execute task. Called when node_online signal is received.
    """
    # Automatic switch to online status happens via node_worker_status_update, which is always accompanied by
    # fast worker startup. So we don't need to react to this signal
    if not kwargs.get('automatic', False):
        user_id, owner_id = user_owner_ids_from_task_id(task_id)
        execute_sysinfo(user_id, owner_id, node.fast_queue, node.uuid)
