from api.event import Event


class VmReplicaSynced(Event):
    """
    Event dispatched by vm_replica_sync_cb after success
    """
    _name_ = 'vm_replica_synced'
