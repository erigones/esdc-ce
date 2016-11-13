from vms.models import Vm
from api.exceptions import VmIsNotOperational, VmIsLocked, OperationNotSupported

VM_STATUS_OPERATIONAL = frozenset([Vm.NOTCREATED, Vm.RUNNING, Vm.STOPPED, Vm.STOPPING])


def is_vm_kvm(fun):
    """Decorator for checking if VM is KVM"""
    def wrap(view, vm, *args, **kwargs):
        if not vm.is_kvm():
            raise OperationNotSupported
        return fun(view, vm, *args, **kwargs)
    return wrap


def is_vm_operational(fun):
    """Decorator for checking VM status"""
    def wrap(view, vm, *args, **kwargs):
        if vm.locked:
            raise VmIsLocked
        if vm.status not in VM_STATUS_OPERATIONAL:
            raise VmIsNotOperational
        return fun(view, vm, *args, **kwargs)
    return wrap
