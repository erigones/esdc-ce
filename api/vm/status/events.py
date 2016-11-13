from api.event import Event


class VmStatusChanged(Event):
    """
    Inform users (VM owners logged in GUI) when VM changes its state.
    """
    _name_ = 'vm_status_changed'

    def __init__(self, task_id, vm):
        status_display = vm.status_display(pending=False)
        super(VmStatusChanged, self).__init__(
            task_id,
            vm_hostname=vm.hostname,
            alias=vm.alias,
            status=vm.status,
            status_display=status_display,
            detail=status_display,  # for logging detail
            status_change=str(vm.status_change),
            define_changed=vm.json_changed(),
            locked=vm.locked,
        )
