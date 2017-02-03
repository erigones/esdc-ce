from logging import getLogger

from django.conf import settings
from django.utils.translation import ugettext_noop as _
from django.core.exceptions import ObjectDoesNotExist

from api.api_views import TaskAPIView
from api.views import exception_handler
from api.exceptions import (PermissionDenied, PreconditionRequired, ExpectationFailed, NodeIsNotOperational,
                            VmIsNotOperational)
from api.task.response import SuccessTaskResponse, FailureTaskResponse, TaskResponse
from api.utils.db import get_virt_object
from api.image.base.serializers import ImageSerializer, ExtendedImageSerializer, ImportImageSerializer
from api.image.base.utils import wait_for_delete_node_image_tasks
from api.image.messages import LOG_IMAGE_IMPORT, LOG_IMAGE_CREATE, LOG_IMAGE_UPDATE, LOG_IMAGE_DELETE
from api.node.image.api_views import IMAGE_TASK_EXPIRES, NodeImageView
from api.dc.utils import attach_dc_virt_object
from api.dc.messages import LOG_IMAGE_ATTACH
from vms.models import Image, ImageVm
from gui.models.permission import ImageImportAdminPermission
from que import TG_DC_UNBOUND

logger = getLogger(__name__)


class ImageView(TaskAPIView):
    """
    This view is always DC-unbound, but the request.dc can change according to image.dc_bound attribute -
    this is going to affect the DC in task_id, which is important for socket.io and callbacks.
    WARNING: This view may change the request.dc attribute!
    """
    dc_bound = False
    order_by_default = ('name',)
    order_by_fields = ('name', 'created')
    img_server = None

    def __init__(self, request, name, data):
        super(ImageView, self).__init__(request)
        self.data = data
        self.name = name

        if self.extended:
            pr = ('dc',)
            self.ser_class = ExtendedImageSerializer
        else:
            pr = ()
            self.ser_class = ImageSerializer

        self.img = get_virt_object(request, Image, data=data, pr=pr, many=not name, name=name, order_by=self.order_by)

    def get(self, many=False):
        if many or not self.name:
            if self.full or self.extended:
                if self.img:
                    res = self.ser_class(self.request, self.img, many=True).data
                else:
                    res = []
            else:
                res = list(self.img.values_list('name', flat=True))
        else:
            res = self.ser_class(self.request, self.img).data

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    def _check_img_server(self, must_exist=False):
        try:
            self.img_server = ImageVm()

            if self.img_server:
                img_vm = self.img_server.vm

                if img_vm.status not in (img_vm.RUNNING, img_vm.STOPPED):
                    raise ObjectDoesNotExist
            elif must_exist:
                raise ObjectDoesNotExist
            else:
                logger.warning('Image server is disabled!')

        except ObjectDoesNotExist:
            raise PreconditionRequired(_('Image server is not available'))

    def _check_img_node(self):
        if self.img_server and self.img_server.node.status != self.img_server.node.ONLINE:
            raise NodeIsNotOperational
        # The vm.node should be checked by get_vm()

    def _check_img(self):
        if self.img.status != Image.OK:
            raise ExpectationFailed('Image status is not OK')

    def _run_checks(self, img_server_must_exist=False):
        self._check_img_server(must_exist=img_server_must_exist)
        self._check_img_node()
        self._check_img()
        # self.img_server is set to ImageVm() at this point, but this does not mean that we have an image server

    def _run_execute(self, msg, cmd, recover_on_error=False, delete_on_error=False, error_fun=None, vm=None, snap=None,
                     detail_dict=None, stdin=None, cmd_add=None, cb_add=None):
        exc = None
        img, img_server, request = self.img, self.img_server, self.request
        self.obj = img  # self.execute() requirement

        # noinspection PyBroadException
        try:
            cmd += ' -d %s >&2' % img_server.datasets_dir

            if cmd_add:
                cmd += cmd_add

            lock = 'image_manage %s' % img.uuid
            callback = ('api.image.base.tasks.image_manage_cb', {'image_uuid': img.uuid})
            apiview = {'view': 'image_manage', 'method': request.method, 'name': img.name}
            meta = {
                'msg': msg,
                'output': {'returncode': 'returncode', 'stderr': 'message', 'stdout': 'json'},
                'replace_text': [(img.uuid, img.name)],
                'image_uuid': img.uuid,
                'apiview': apiview,
            }

            if cb_add:
                callback[1].update(cb_add)

            if vm:  # image_snapshot view
                meta['vm_uuid'] = vm.uuid
                meta['replace_text'].append((vm.uuid, vm.hostname))
                callback[1]['vm_uuid'] = vm.uuid
                callback[1]['snap_id'] = snap.id
                apiview['view'] = 'image_snapshot'
                snap_data = {'hostname': vm.hostname, 'snapname': snap.name, 'disk_id': snap.array_disk_id}
                apiview.update(snap_data)
                detail_dict.update(snap_data)

            if self.execute(cmd, meta=meta, lock=lock, callback=callback, tg=TG_DC_UNBOUND,
                            queue=img_server.node.image_queue, stdin=stdin, expires=IMAGE_TASK_EXPIRES):
                if request.method == 'POST' and img.dc_bound:
                    attach_dc_virt_object(self.task_id, LOG_IMAGE_ATTACH, img, img.dc_bound, user=request.user)

                return TaskResponse(request, self.task_id, msg=msg, obj=img, api_view=apiview, detail_dict=detail_dict,
                                    data=self.data)
        except Exception as exc:
            pass

        # Rollback + return error response
        if error_fun:
            error_fun()

        if delete_on_error:
            img.delete()
        else:
            if recover_on_error:
                for attr, value in img.backup.items():
                    setattr(img, attr, value)

                img.backup = {}  # Remove backup
                img.manifest = img.manifest_active
                img.status = Image.OK
                img.save()
            else:
                img.save_status(Image.OK)

        if exc:  # This should never happen
            raise exc

        return FailureTaskResponse(request, self.error, obj=img, dc_bound=self.dc_bound)

    def create(self, vm, snap):
        """Create [POST] image from VM snapshot (ImageAdmin).

        This is always a DC bound task, but the task_id has a DC_UNBOUND task group flag,
        because socket.io will inform any admin regardless of the current admin DC.
        The callback is responsible for attaching the image into current DC.
        """
        img, data, request = self.img, self.data, self.request

        assert request.dc == vm.dc

        if vm.uuid in settings.VMS_INTERNAL:  # Bug #chili-792
            raise PreconditionRequired('Internal VM can\'t be used for creating images')

        data.pop('dc_bound', None)  # Default DC binding cannot be changed when creating Image for the first time
        img.dc_bound = vm.dc        # Default DC binding set to VM DC (cannot be changed, ^^^)
        img.ostype = vm.ostype      # Default ostype inherited from VM (cannot be changed)
        img.size = snap.disk_size   # Default disk size inherited from VM (cannot be changed)
        img.owner = request.user    # Default user (can be changed)
        img.alias = img.name        # Default alias (can be changed)
        img.status = Image.OK       # Set status for preliminary checks
        # Validate data (manifest info)
        ser = ImageSerializer(request, img, data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, dc_bound=self.dc_bound)

        # Preliminary checks
        self._run_checks(img_server_must_exist=True)  # This sets self.img_server to ImageVm()

        if vm.status not in (vm.RUNNING, vm.STOPPED, vm.STOPPING, vm.FROZEN):
            raise VmIsNotOperational

        if snap.status != snap.OK:
            raise ExpectationFailed('VM snapshot status is not OK')

        # Build manifest and set PENDING status
        # noinspection PyUnusedLocal
        data = ser.data
        img.manifest = img.build_manifest()
        img.status = Image.PENDING
        img.src_vm = vm
        img.src_snap = snap
        img.save()
        # Set snapshot status to PENDING
        snap.save_status(snap.PENDING)
        # Build command
        cmd_add = ' ; e=$?; cat %s/%s/manifest 2>&1; exit $e' % (self.img_server.datasets_dir, img.uuid)
        cmd = 'esimg create -s %s@%s' % (snap.zfs_filesystem, snap.zfs_name)

        if self.img_server.node != vm.node:
            cmd += ' -H %s' % vm.node.address

        return self._run_execute(LOG_IMAGE_CREATE, cmd, stdin=img.manifest.dump(), delete_on_error=True, vm=vm,
                                 snap=snap, error_fun=lambda: snap.save_status(snap.OK), detail_dict=ser.detail_dict(),
                                 cmd_add=cmd_add)

    def post(self):
        """Import [POST] image from URL.

        This is always a DC bound task, but the task_id has a DC_UNBOUND task group flag,
        because socket.io will inform any admin regardless of the current admin DC.
        The callback is responsible for attaching the image into current DC if the image is dc_bound.
        """
        img, data, request = self.img, self.data, self.request

        # ImageImportAdmin permission is required
        if not request.user.has_permission(request, ImageImportAdminPermission.name):
            raise PermissionDenied

        # Validate URL and file URL
        ser_import = ImportImageSerializer(img, data=data)

        if not ser_import.is_valid():
            return FailureTaskResponse(request, ser_import.errors, dc_bound=self.dc_bound)

        if not request.user.is_staff:
            self.data.pop('dc_bound', None)  # default DC binding cannot be changed when creating object

        img.manifest = ser_import.manifest  # Load imported manifest
        img.owner = request.user    # Default user (can be changed)
        img.alias = img.name        # Default alias (can be changed)
        img.status = Image.OK       # Set status for preliminary checks

        # More default fields retrieved from the downloaded image manifest
        for img_field in ('version', 'desc', 'resize', 'deploy', 'tags'):
            if img_field not in data:
                def_value = getattr(img, img_field, None)
                if def_value:
                    data[img_field] = def_value

        # Validate data for overriding manifest info
        ser = ImageSerializer(request, img, data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, dc_bound=self.dc_bound)

        # Preliminary checks
        self._run_checks()
        # Build new manifest
        img.manifest = img.build_manifest()
        # Add URL into detail dict
        ser_data = ser.data
        dd = ser.detail_dict()
        dd.update(ser_import.detail_dict())

        if self.img_server:
            img.status = Image.PENDING
            img.save()

            return self._run_execute(LOG_IMAGE_IMPORT, 'esimg import -f %s' % ser_import.img_file_url,
                                     stdin=img.manifest.dump(), delete_on_error=True, detail_dict=dd)
        else:
            img.status = Image.OK
            img.manifest_active = img.manifest
            img.save()

            return SuccessTaskResponse(self.request, ser_data, obj=img, msg=LOG_IMAGE_IMPORT,
                                       detail_dict=dd, dc_bound=self.dc_bound)

    def put(self):
        """Update [PUT] image manifest in DB and on image server if needed.

        The task group is always DC unbound, but the current DC depends on the dc_bound flag:
            - dc_bound=False:   task DC is default DC
            - dc_bound=[DC]:    task DC is dc_bound DC
        The callback is responsible for restoring the active manifest if something goes wrong.
        """
        img = self.img
        ser = ImageSerializer(self.request, img, self.data, partial=True)
        img_backup = ser.create_img_backup()

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, dc_bound=self.dc_bound)

        # Preliminary checks
        self._run_checks()  # This sets self.img_server to ImageVm()
        ser_data = ser.data

        if ser.update_manifest:
            # Rebuild manifest
            img.manifest = img.build_manifest()

        if self.img_server and ser.update_manifest:
            img.status = Image.PENDING
            img.backup = img_backup
            img.save()

            return self._run_execute(LOG_IMAGE_UPDATE, 'esimg update', stdin=img.manifest.dump(),
                                     recover_on_error=img_backup, detail_dict=ser.detail_dict())
        else:
            # Just save new data
            img.manifest_active = img.manifest
            img.save()

            return SuccessTaskResponse(self.request, ser_data, obj=img, msg=LOG_IMAGE_UPDATE,
                                       detail_dict=ser.detail_dict(), dc_bound=self.dc_bound)

    def delete(self):
        """Delete [DELETE] image from DB and from Image server.

        The task group is always DC unbound, but the current DC depends on the dc_bound flag:
            - dc_bound=False:   task DC is default DC
            - dc_bound=[DC]:    task DC is dc_bound DC
        The callback is responsible for detaching the image from each DC and deleting it from DB.
        """
        request, img, data = self.request, self.img, self.data

        # Check if image is used by som VMs
        if img.is_used_by_vms():
            raise PreconditionRequired(_('Image is used by some VMs'))

        # Preliminary checks
        self._run_checks()  # This sets self.img_server to ImageVm()

        request.disable_throttling = True
        delete_node_image_tasks = []

        # Run task for removing the image from all NodeStorages which have the image imported locally
        for ns in img.nodestorage_set.select_related('node').all():
            # We need to bypass the permission checks, because node_image can be called by SuperAdmin only
            try:
                res = NodeImageView(request, ns, img, data).delete()
            except Exception as ex:
                res = exception_handler(ex, request)
                if res is None:
                    raise
                res.exception = True
                logger.error('DELETE node_image(%s, %s, %s) failed (%s): %s',
                             ns.node.hostname, ns.zpool, img.name, res.status_code, res.data)
            else:
                logger.info('DELETE node_image(%s, %s, %s) was successful (%s): %s',
                            ns.node.hostname, ns.zpool, img.name, res.status_code, res.data)

            if res.status_code == 200:
                continue
            elif res.status_code == 201:
                delete_node_image_tasks.append(res.data['task_id'])
            else:
                return res

        if self.img_server:
            # Set PENDING status
            img.save_status(Image.PENDING)

            return self._run_execute(LOG_IMAGE_DELETE, 'esimg delete -u %s' % img.uuid,
                                     cb_add={'delete_node_image_tasks': delete_node_image_tasks})

        else:
            if wait_for_delete_node_image_tasks(img, delete_node_image_tasks, timeout=30):
                obj = img.log_list
                owner = img.owner
                img.delete()

                return SuccessTaskResponse(self.request, None, obj=obj, owner=owner, msg=LOG_IMAGE_DELETE,
                                           dc_bound=self.dc_bound)
            else:
                raise PreconditionRequired(_('Image is being deleted from compute node storages; Try again later'))
