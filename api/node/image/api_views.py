from logging import getLogger
from dateutil.parser import parse
from django.utils.translation import ugettext_noop as _
from django.utils.six import iteritems

from api.api_views import APIView
from api.views import exception_handler
from api.utils.views import call_api_view
from api.utils.request import set_request_method
from api.exceptions import (ObjectAlreadyExists, PreconditionRequired, NodeIsNotOperational, ExpectationFailed,
                            FailedDependency)
from api.task.utils import get_task_error_message
from api.task.response import TaskResponse, SuccessTaskResponse, FailureTaskResponse
from api.node.messages import LOG_IMG_IMPORT, LOG_IMG_DELETE
from api.node.image.serializers import NodeImageSerializer, ExtendedNodeImageSerializer
from vms.models import Image
from que import TG_DC_UNBOUND
from que.tasks import execute

# An image task can wait for a free image worker for up to 1 hour
IMAGE_TASK_EXPIRES = 3600

logger = getLogger(__name__)


class NodeImageView(APIView):
    dc_bound = False
    order_by_default = order_by_fields = ('name',)

    def __init__(self, request, ns, img, data):
        super(NodeImageView, self).__init__(request)
        self.ns = ns
        self.img = img
        self.data = data

    @classmethod
    def import_for_vm(cls, request, ns, img, vm):
        """Import image required by VM. Return block_key or raise a FailedDependency API Exception (424)."""
        node = ns.node
        logger.warn('Image %s required for VM %s must be imported to node=%s, zpool=%s', img.name, vm, node, ns.zpool)
        img_ns_status = img.get_ns_status(ns)

        if img_ns_status == img.DELETING:  # Someone is currently removing the image from node pool
            # We can't do anything about this
            raise ExpectationFailed('Required disk image is processed by another task')

        block_key = img.get_block_key(ns)

        if img_ns_status == img.IMPORTING:
            logger.warn('Image %s is being imported to node=%s, zpool=%s; vm_manage will be blocked by block_key=%s',
                        img, node, ns.zpool, block_key)
            return block_key

        old_method = request.method

        try:
            request = set_request_method(request, 'POST')
            res = cls(request, ns, img, None).post()
        except Exception as ex:
            res = exception_handler(ex, request)
            if res is None:
                raise ex
            res.exception = True
        finally:
            set_request_method(request, old_method)

        if res.status_code in (200, 201):
            logger.warn('POST node_image(%s, %s, %s) was successful: %s; task will be blocked by block_key=%s',
                        node.hostname, ns.zpool, img.name, res.data, block_key)
            return block_key
        else:
            logger.error('POST node_image(%s, %s, %s) failed: %s (%s): %s; raising 424 API exception',
                         node.hostname, ns.zpool, img.name, res.status_code, res.status_text, res.data)
            errmsg = get_task_error_message(res.data)
            raise FailedDependency('Cannot import required image %s to node %s (%s: %s)' % (img.name, node.hostname,
                                                                                            res.status_code, errmsg))

    @staticmethod
    def _get_image_vms_map(ns):
        image_vms = {}

        for vm in ns.node.vm_set.select_related('dc').all().order_by('hostname'):
            for img_uuid in vm.get_image_uuids(zpool=ns.zpool):
                image_vms.setdefault(img_uuid, []).append({'hostname': vm.hostname, 'dc': vm.dc.name})

        return image_vms

    @staticmethod
    def _get_image_vms(image_vms, img):
        return [v for k, v in iteritems(image_vms) if img.uuid in k]

    def get(self, many=False):
        """Show image details"""
        img = self.img

        if self.extended:
            serializer = ExtendedNodeImageSerializer
            image_vms = self._get_image_vms_map(self.ns)

            if many:
                for i in img:
                    i.vms = self._get_image_vms(image_vms, i)
            else:
                img.vms = self._get_image_vms(image_vms, img)
        else:
            serializer = NodeImageSerializer

        if many:
            if self.full or self.extended:
                if img:
                    # noinspection PyUnresolvedReferences
                    res = serializer(self.request, img, many=True).data
                else:
                    res = []
            else:
                res = list(img.values_list('name', flat=True))
        else:
            # noinspection PyUnresolvedReferences
            res = serializer(self.request, img).data

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    def _check_img(self):
        img = self.img

        if img.status != img.OK:
            raise ExpectationFailed('Image status is not OK')

        if img.get_ns_status(self.ns) != img.READY:
            raise ExpectationFailed('Image is not ready')

    def _check_node(self):
        node = self.ns.node

        if node.status != node.ONLINE:
            raise NodeIsNotOperational

    def _check_platform_version(self):
        """Issue #chili-937 & Issue #chili-938"""
        min_version, max_version = self.img.min_platform, self.img.max_platform

        if min_version or max_version:
            node_version = parse(self.ns.node.platform_version)

            if min_version:
                if parse(min_version) > node_version:
                    raise PreconditionRequired('Image requires newer node version')

            if max_version:
                if parse(max_version) < node_version:
                    raise PreconditionRequired('Image requires older node version')

    def _run_execute(self, msg, cmd, status):
        self._check_img()

        request, ns, img = self.request, self.ns, self.img
        node = ns.node
        detail = 'image=%s' % img.name
        apiview = {
            'view': 'node_image',
            'method': request.method,
            'hostname': node.hostname,
            'zpool': ns.zpool,
            'name': img.name,
        }
        # Set importing/deleting status
        img.set_ns_status(ns, status)
        # Create task
        tid, err = execute(request, ns.storage.owner.id, cmd,
                           tg=TG_DC_UNBOUND,
                           queue=node.image_queue,
                           meta={'output': {'returncode': 'returncode', 'stdout': 'message'},
                                 'replace_stdout': ((node.uuid, node.hostname), (img.uuid, img.name)),
                                 'msg': msg, 'nodestorage_id': ns.id, 'apiview': apiview},
                           callback=('api.node.image.tasks.node_image_cb', {'nodestorage_id': ns.id, 'zpool': ns.zpool,
                                                                            'img_uuid': img.uuid}),
                           lock='node_image ns:%s img:%s' % (ns.id, img.uuid),  # Lock image per node storage
                           expires=IMAGE_TASK_EXPIRES)

        if err:
            img.del_ns_status(ns)
            return FailureTaskResponse(request, err, obj=ns)
        else:
            return TaskResponse(request, tid, msg=msg, obj=ns, api_view=apiview, detail=detail, data=self.data)

    def post(self):
        self._check_node()
        ns, img = self.ns, self.img

        if img.nodestorage_set.filter(id=ns.id).exists():
            raise ObjectAlreadyExists(model=Image)

        try:
            self._check_platform_version()
        except PreconditionRequired as exc:
            raise exc
        except Exception as exc:
            # An error in this check should not stop us - fail silently
            logger.exception(exc)

        return self._run_execute(LOG_IMG_IMPORT, 'imgadm import -q -P %s %s 2>&1' % (ns.zpool, img.uuid), img.IMPORTING)

    def delete(self):
        self._check_node()
        ns, img = self.ns, self.img
        zpool = ns.zpool

        for vm in ns.node.vm_set.all():
            if img.uuid in vm.get_image_uuids(zpool=zpool):
                raise PreconditionRequired(_('Image is used by some VMs'))

        return self._run_execute(LOG_IMG_DELETE, 'imgadm delete -P %s %s 2>&1' % (ns.zpool, img.uuid), img.DELETING)

    def cleanup(self):
        self._check_node()
        ns = self.ns
        zpool = ns.zpool
        used_images = set()

        for vm in ns.node.vm_set.all():
            used_images.update(vm.get_image_uuids(zpool=zpool))

        unused_images = self.img.exclude(uuid__in=used_images)
        res = {}
        node_hostname = ns.node.hostname
        from api.node.image.views import node_image

        for img in unused_images:
            if img.get_ns_status(ns) == img.READY:
                r = call_api_view(self.request, 'DELETE', node_image, node_hostname, zpool, img.name, log_response=True)
                res[img.name] = {'status_code': r.status_code, 'response': r.data}

        return SuccessTaskResponse(self.request, res, dc_bound=False)
