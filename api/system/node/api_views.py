from logging import getLogger

from django.conf import settings
from django.utils.six import text_type

from api.api_views import APIView
from api.exceptions import (NodeIsNotOperational, PreconditionRequired, TaskIsAlreadyRunning,
                            ObjectNotFound, GatewayTimeout)
from api.node.utils import get_node, get_nodes
from api.system.messages import LOG_SYSTEM_UPDATE
from api.system.node.serializers import NodeVersionSerializer
from api.system.node.events import NodeUpdateStarted, NodeUpdateFinished
from api.system.service.control import NodeServiceControl
from api.system.update.serializers import UpdateSerializer
from api.system.update.utils import process_update_reply
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from que import TG_DC_UNBOUND, TT_DUMMY, Q_FAST
from que.lock import TaskLock
from que.utils import task_id_from_request, worker_command
from vms.models import DefaultDc


logger = getLogger(__name__)


class NodeVersionView(APIView):
    """api.system.node.views.system_node_version and api.system.node.views.system_node_version_list"""
    dc_bound = False

    def __init__(self, request, hostname, data):
        super(NodeVersionView, self).__init__(request)
        self.hostname = hostname
        self.data = data

        if hostname:
            self.node = get_node(request, hostname)
        else:
            self.node = get_nodes(request)

    def get(self, many=False):
        res = NodeVersionSerializer(self.node, many=many).data

        return SuccessTaskResponse(self.request, res, dc_bound=self.dc_bound)


class NodeServiceStatusView(APIView):
    dc_bound = False

    # noinspection PyUnusedLocal
    def __init__(self, request, hostname, service, data=None):
        super(NodeServiceStatusView, self).__init__(request)
        self.service = service
        self.hostname = hostname
        self.data = data
        self.node = get_node(request, hostname)
        self.ctrl = NodeServiceControl(self.node)

        if service and service not in self.ctrl.services:
            raise ObjectNotFound(object_name='Service')

    def get(self):
        """Return service status or a list of all service statuses"""
        if self.service:
            res = self.ctrl.status(self.service)
        else:
            res = self.ctrl.status_all()

        return SuccessTaskResponse(self.request, res, dc_bound=False)


class NodeUpdateView(APIView):
    """api.system.node.views.system_node_update"""
    dc_bound = False
    _lock_key = 'system_update'

    def __init__(self, request, hostname, data):
        super(NodeUpdateView, self).__init__(request)
        self.hostname = hostname
        self.data = data
        self.node = get_node(request, hostname)
        self.task_id = task_id_from_request(self.request, dummy=True, tt=TT_DUMMY, tg=TG_DC_UNBOUND)

    def _update(self, version, key=None, cert=None):
        node = self.node
        worker = node.worker(Q_FAST)
        logger.debug('Running node "%s" system update to version: "%s"', node, version)
        reply = worker_command('system_update', worker, version=version, key=key, cert=cert, timeout=600)

        if reply is None:
            raise GatewayTimeout('Node worker is not responding')

        response_class, result = process_update_reply(reply, node, version)
        response = response_class(self.request, result, task_id=self.task_id, obj=node, msg=LOG_SYSTEM_UPDATE,
                                  detail_dict=result, dc_bound=False)

        if response.status_code == 200:
            # Restart all erigonesd workers
            ctrl = NodeServiceControl(node)

            for service in ctrl.app_services:
                ctrl.restart(service)

        return response

    @classmethod
    def get_task_lock(cls):
        # Also used in socket.io namespace
        return TaskLock(cls._lock_key, desc='System task')

    def put(self):
        assert self.request.dc.id == DefaultDc().id

        ser = UpdateSerializer(self.request, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, task_id=self.task_id, dc_bound=False)

        node = self.node
        version = ser.object['version']

        node_version = node.system_version

        if not (isinstance(node_version, text_type) and node_version):
            raise NodeIsNotOperational('Node version information could not be retrieved')

        if version == ('v' + node.system_version):
            raise PreconditionRequired('Node is already up-to-date')

        if node.status != node.OFFLINE:
            raise NodeIsNotOperational('Unable to perform update on node that is not in OFFLINE state!')

        lock = self.get_task_lock()

        if not lock.acquire(self.task_id, timeout=7200, save_reverse=False):
            raise TaskIsAlreadyRunning

        try:
            # Emit event into socket.io
            NodeUpdateStarted(self.task_id, request=self.request).send()

            return self._update(version, key=ser.object.get('key'), cert=ser.object.get('cert'))
        finally:
            lock.delete(fail_silently=True, delete_reverse=False)
            del node.system_version
            # Emit event into socket.io
            NodeUpdateFinished(self.task_id, request=self.request).send()


class NodeLogsView(APIView):
    """api.system.node.views.system_node_logs"""
    dc_bound = False
    log_path = settings.LOGDIR
    # hardcoded default log files that will be retrieved
    log_files = (
        'fast.log',
        'slow.log',
        'image.log',
        'backup.log',
    )

    def __init__(self, request, hostname, data):
        super(NodeLogsView, self).__init__(request)
        self.node = get_node(request, hostname)
        self.data = data

    # noinspection PyUnusedLocal
    def get(self, many=False):
        """Function retrieves predefined log files from worker"""
        if not self.node.is_online():
            raise NodeIsNotOperational()

        single_log_file = self.data.get('logname', None)

        if single_log_file:
            # make sure that file is among allowed files,
            # otherwise any file with read permission can be retrieved
            if single_log_file in self.log_files:
                self.log_files = (single_log_file, )
            else:
                logger.error('Error retrieving log file %s, file not among allowed files!', single_log_file)
                raise ObjectNotFound(object_name=single_log_file)

        worker = self.node.worker('fast')
        logger.debug('Retrieving log files from node "%s"', self.node)
        log_files_result = worker_command('system_read_logs', worker, log_files=self.log_files, timeout=10)

        if log_files_result is None:
            raise GatewayTimeout('Node worker is not responding')

        return SuccessTaskResponse(self.request, log_files_result, dc_bound=self.dc_bound)
