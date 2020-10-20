from django.db.transaction import atomic

from api import status as scode
from api.fields import get_boolean_value
from api.utils.db import get_listitem
from api.utils.request import set_request_method
from api.exceptions import OperationNotSupported
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.vm.define.utils import is_vm_operational
from api.vm.define.api_views import VmDefineBaseView
from api.vm.define.serializers import VmDefineDiskSerializer
from api.vm.messages import LOG_DISK_CREATE, LOG_DISK_UPDATE, LOG_DISK_DELETE

DISK_ID_MIN = 0
DISK_ID_MAX = 1  # Bug #chili-462
DISK_ID_MAX_BHYVE = 3
DISK_ID_MAX_OS = 1


def _disk_params(fun):
    """Decorator for disk functions below"""
    def wrap(view, vm, disk_id, *args, **kwargs):
        if disk_id is None and view.diff:
            return SuccessTaskResponse(view.request, view.get_diff(vm))

        if view.active:
            vm.revert_active(json_only=True)

        if disk_id is None:
            disk = vm.json_get_disks()
            disks = None
            kwargs['many'] = True
        else:
            if vm.is_bhyve():
                disk_id_max = DISK_ID_MAX_BHYVE
            elif vm.is_hvm():
                disk_id_max = DISK_ID_MAX
            else:
                disk_id_max = DISK_ID_MAX_OS

            disks, disk = get_listitem(view.request, vm.json_get_disks(), disk_id, name='VM disk',
                                       max_value=disk_id_max, min_value=DISK_ID_MIN)

        return fun(view, vm, disk_id, disks, disk, *args, **kwargs)

    return wrap


class VmDefineDiskView(VmDefineBaseView):

    @staticmethod
    def _image_tags_inherit(data):
        return data is None or get_boolean_value(data.get('image_tags_inherit', True))

    def _set_vm_tags(self, vm, tags, task_id=None):
        from api.vm.define.vm_define import VmDefineView

        request = set_request_method(self.request, 'PUT')
        VmDefineView(request).put(vm, {'tags': list(tags)}, task_id=task_id)

    def _update_vm_tags(self, vm, img, img_old, data, task_id=None):
        if self._image_tags_inherit(data) and (img or img_old) and (img != img_old):
            vm_tags = set(vm.tag_list)
            vm_tags_new = vm_tags.copy()

            if img_old:
                img_old_tags = set(img_old.tags)

                if img_old_tags.issubset(vm_tags):
                    vm_tags_new = vm_tags - img_old_tags

            if img:
                vm_tags_new.update(img.tags)

            if vm_tags != vm_tags_new:
                self._set_vm_tags(vm, vm_tags_new, task_id=task_id)

    def _delete_vm_tags(self, vm, img, data, task_id=None):
        if img and self._image_tags_inherit(data):
            img_tags, vm_tags = set(img.tags), set(vm.tag_list)

            if img_tags and img_tags.issubset(vm_tags):
                self._set_vm_tags(vm, list(vm_tags - img_tags), task_id=task_id)

    def get_diff(self, vm):
        """Show disk differences between active and in db json. Implies full and denies active vm_define_disk."""
        def_current = VmDefineDiskSerializer(self.request, vm, vm.json_get_disks(), disk_id=None, many=True).data
        def_active = VmDefineDiskSerializer(self.request, vm, vm.json_active_get_disks(), disk_id=None, many=True).data

        return self._diff_lists(def_active, def_current)

    # noinspection PyUnusedLocal
    @_disk_params
    def get(self, vm, disk_id, disks, disk, data, many=False):
        """Get VM disk definition"""
        ser = VmDefineDiskSerializer(self.request, vm, disk, disk_id=disk_id, many=many)

        return SuccessTaskResponse(self.request, ser.data, vm=vm)

    # noinspection PyUnusedLocal
    @is_vm_operational
    @atomic
    @_disk_params
    def post(self, vm, disk_id, disks, disk, data):
        """Create VM nic definition"""
        if not vm.is_hvm() and vm.is_deployed():
            raise OperationNotSupported

        ser = VmDefineDiskSerializer(self.request, vm, disk_id=disk_id, data=data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, vm=vm)

        disks[disk_id] = ser.jsondata
        vm.save_disks(disks, update_node_resources=ser.update_node_resources,
                      update_storage_resources=ser.update_storage_resources)
        res = SuccessTaskResponse(self.request, ser.data, status=scode.HTTP_201_CREATED, vm=vm, msg=LOG_DISK_CREATE,
                                  detail='disk_id=' + str(disk_id + 1), detail_dict=ser.detail_dict())
        self._update_vm_tags(vm, ser.img, ser.img_old, data, task_id=res.data.get('task_id'))

        return res

    @is_vm_operational
    @atomic
    @_disk_params
    def put(self, vm, disk_id, disks, disk, data):
        """Update VM disk definition"""
        ser = VmDefineDiskSerializer(self.request, vm, disk.copy(), disk_id=disk_id, data=data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, vm=vm)

        disks[disk_id] = ser.jsondata
        vm.save_disks(disks, update_node_resources=ser.update_node_resources,
                      update_storage_resources=ser.update_storage_resources)
        res = SuccessTaskResponse(self.request, ser.data, vm=vm, msg=LOG_DISK_UPDATE,
                                  detail='disk_id=' + str(disk_id + 1), detail_dict=ser.detail_dict())
        self._update_vm_tags(vm, ser.img, ser.img_old, data, task_id=res.data.get('task_id'))

        return res

    # noinspection PyUnusedLocal
    @is_vm_operational
    @atomic
    @_disk_params
    def delete(self, vm, disk_id, disks, disk, data):
        """Delete VM disk definition"""
        if not vm.is_hvm() and (disk_id == 0 or vm.is_deployed()):
            raise OperationNotSupported

        ser = VmDefineDiskSerializer(self.request, vm, disk, disk_id=disk_id)
        del disks[disk_id]
        ns = ser.get_node_storage(ser.object.get('zpool'), vm.node)

        if ns:
            update_storage_resources = [ns]
        else:
            update_storage_resources = []

        vm.save_disks(disks, update_node_resources=True, update_storage_resources=update_storage_resources)
        res = SuccessTaskResponse(self.request, None, vm=vm, detail='disk_id=' + str(disk_id + 1), msg=LOG_DISK_DELETE)
        self._delete_vm_tags(vm, ser.img_old, data, task_id=res.data.get('task_id'))

        return res
