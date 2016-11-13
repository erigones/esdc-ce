from que.utils import ping


def node_ping(node, timeout=True, count=2, all_workers=True, all_up=True):
    """Ping all relevant node workers to check if node is UP"""
    up = 0
    queues = [node.fast_queue, node.image_queue]  # Base workers

    if all_workers:  # Additional workers depend on node capabilities
        if node.is_compute:
            queues.append(node.slow_queue)

        if node.is_backup:
            queues.append(node.backup_queue)

    for q in queues:
        if ping(q, timeout=timeout, count=count):
            up += 1

    if all_up:
        return up == len(queues)
    else:
        return bool(up)
