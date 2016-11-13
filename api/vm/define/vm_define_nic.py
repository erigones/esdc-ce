from django.db.transaction import atomic

from api import status as scode
from api.utils.db import get_listitem
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.vm.define.utils import is_vm_operational
from api.vm.define.api_views import VmDefineBaseView
from api.vm.define.serializers import VmDefineNicSerializer
from api.vm.messages import LOG_NIC_CREATE, LOG_NIC_UPDATE, LOG_NIC_DELETE

NIC_ID_MIN = 0
NIC_ID_MAX = 5


def _nic_params(fun):
    """Decorator for nic functions below"""
    def wrap(view, vm, nic_id, *args, **kwargs):
        if nic_id is None and view.diff:
            return SuccessTaskResponse(view.request, view.get_diff(vm))

        if view.active:
            vm.revert_active(json_only=True)

        if nic_id is None:
            nic = vm.json_get_nics()
            nics = None
            kwargs['many'] = True
        else:
            nics, nic = get_listitem(view.request, vm.json_get_nics(), nic_id, name='VM NIC',
                                     max_value=NIC_ID_MAX, min_value=NIC_ID_MIN)

        return fun(view, vm, nic_id, nics, nic, *args, **kwargs)

    return wrap


class VmDefineNicView(VmDefineBaseView):

    def get_diff(self, vm):
        """Show nic differences between active and in db json. Implies full and denies active vm_define_nic."""
        def_current = VmDefineNicSerializer(self.request, vm, vm.json_get_nics(), nic_id=None, many=True).data
        def_active = VmDefineNicSerializer(self.request, vm, vm.json_active_get_nics(), nic_id=None, many=True).data

        return self._diff_lists(def_active, def_current)

    # noinspection PyUnusedLocal
    @_nic_params
    def get(self, vm, nic_id, nics, nic, data, many=False):
        """Get VM nic definition"""
        ser = VmDefineNicSerializer(self.request, vm, nic, nic_id=nic_id, many=many)

        return SuccessTaskResponse(self.request, ser.data, vm=vm)

    # noinspection PyUnusedLocal
    @is_vm_operational
    @atomic
    @_nic_params
    def post(self, vm, nic_id, nics, nic, data):
        """Create VM nic definition"""
        ser = VmDefineNicSerializer(self.request, vm, nic_id=nic_id, data=data)

        if ser.is_valid():
            nics[nic_id] = ser.jsondata
            vm.resolvers = ser.resolvers
            vm.save_nics(nics, monitoring_ip=ser.get_monitoring_ip())
            res = SuccessTaskResponse(self.request, ser.data,
                                      status=scode.HTTP_201_CREATED, vm=vm,
                                      detail='nic_id=' + str(nic_id + 1), detail_dict=ser.detail_dict(),
                                      msg=LOG_NIC_CREATE)
            ser.save_ip(res.data.get('task_id'))  # Always save ip.vm

            return res

        return FailureTaskResponse(self.request, ser.errors, vm=vm)

    @is_vm_operational
    @atomic
    @_nic_params
    def put(self, vm, nic_id, nics, nic, data):
        """Update VM nic definition"""
        ser = VmDefineNicSerializer(self.request, vm, nic.copy(), nic_id=nic_id, data=data, partial=True)

        if ser.is_valid():
            nics[nic_id].update(ser.jsondata)
            vm.resolvers = ser.resolvers
            vm.save_nics(nics, monitoring_ip=ser.get_monitoring_ip())
            res = SuccessTaskResponse(self.request, ser.data, vm=vm,
                                      detail='nic_id=' + str(nic_id + 1), detail_dict=ser.detail_dict(),
                                      msg=LOG_NIC_UPDATE)
            ser.update_ip(res.data.get('task_id'))  # Always update ip.vm

            return res

        return FailureTaskResponse(self.request, ser.errors, vm=vm)

    # noinspection PyUnusedLocal
    @is_vm_operational
    @atomic
    @_nic_params
    def delete(self, vm, nic_id, nics, nic, data):
        """Delete VM nic definition"""
        ser = VmDefineNicSerializer(self.request, vm, nic)
        del nics[nic_id]
        vm.save_nics(nics, monitoring_ip=ser.get_monitoring_ip(delete=True))
        res = SuccessTaskResponse(self.request, None, vm=vm,
                                  detail='nic_id=' + str(nic_id + 1),
                                  msg=LOG_NIC_DELETE)
        ser.delete_ip(res.data.get('task_id'))  # Set ip.vm to None

        return res
