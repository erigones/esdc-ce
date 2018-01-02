from logging import getLogger

from django.conf import settings
from django.utils.six import text_type

from api.api_views import APIView
# noinspection PyProtectedMember
from api.fields import get_boolean_value
from api.exceptions import NodeIsNotOperational, PreconditionRequired, ObjectNotFound, GatewayTimeout
from api.node.utils import get_node, get_nodes
from api.system.messages import LOG_SYSTEM_UPDATE
from api.system.node.serializers import NodeVersionSerializer
from api.system.service.control import NodeServiceControl
from api.system.update.serializers import UpdateSerializer
from api.task.response import SuccessTaskResponse, FailureTaskResponse, TaskResponse
from que import Q_FAST, TG_DC_UNBOUND
from que.utils import worker_command
from que.tasks import execute


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

            if self.data and get_boolean_value(self.data.get('fresh', None)):
                del self.node.system_version  # Remove cached version information
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
    LOCK = 'system_node_update:%s'
    dc_bound = False

    def __init__(self, request, hostname, data):
        super(NodeUpdateView, self).__init__(request)
        self.hostname = hostname
        self.data = data
        self.node = get_node(request, hostname)

    def _update_v2(self, version, key=None, cert=None):
        from api.system.update.utils import process_update_reply

        node = self.node
        worker = node.worker(Q_FAST)
        logger.info('Running oldstyle (v2.x) node "%s" system update to version: "%s"', node, version)
        reply = worker_command('system_update', worker, version=version, key=key, cert=cert, timeout=600)

        if reply is None:
            raise GatewayTimeout('Node worker is not responding')

        result, error = process_update_reply(reply, node, version)

        if error:
            response_class = FailureTaskResponse
        else:
            response_class = SuccessTaskResponse

        detail_dict = result.copy()
        detail_dict['version'] = version
        response = response_class(self.request, result, obj=node, msg=LOG_SYSTEM_UPDATE, dc_bound=False,
                                  detail_dict=detail_dict)

        if response.status_code == 200:
            # Restart all erigonesd workers
            ctrl = NodeServiceControl(node)

            for service in ctrl.app_services:
                ctrl.restart(service)

        return response

    def put(self):
        assert self.request.dc.is_default()

        ser = UpdateSerializer(self.request, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, dc_bound=False)

        node = self.node
        version = ser.data['version']
        key = ser.data.get('key')
        cert = ser.data.get('cert')
        del node.system_version  # Request latest version in next command
        node_version = node.system_version

        if not (isinstance(node_version, text_type) and node_version):
            raise NodeIsNotOperational('Node version information could not be retrieved')

        node_version = node_version.split(':')[-1]  # remove edition prefix

        if version == ('v' + node_version) and not ser.data.get('force'):
            raise PreconditionRequired('Node is already up-to-date')

        if node.status != node.OFFLINE:
            raise NodeIsNotOperational('Unable to perform update on node that is not in maintenance state')

        if node_version.startswith('2.'):
            # Old-style (pre 3.0) update mechanism
            return self._update_v2(version, key=key, cert=cert)

        # Upload key and cert and get command array
        worker = node.worker(Q_FAST)
        update_cmd = worker_command('system_update_command', worker, version=version, key=key, cert=cert,
                                    force=ser.data.get('force'), timeout=10)

        if update_cmd is None:
            raise GatewayTimeout('Node worker is not responding')

        if not isinstance(update_cmd, list):
            raise PreconditionRequired('Node update command could be retrieved')

        msg = LOG_SYSTEM_UPDATE
        _apiview_ = {
            'view': 'system_node_update',
            'method': self.request.method,
            'hostname': node.hostname,
            'version': version,
        }
        meta = {
            'apiview': _apiview_,
            'msg': msg,
            'node_uuid': node.uuid,
            'output': {'returncode': 'returncode', 'stdout': 'message'},
            'check_returncode': True,
        }
        lock = self.LOCK % node.hostname
        cmd = '%s 2>&1' % ' '.join(update_cmd)

        tid, err = execute(self.request, node.owner.id, cmd, meta=meta, lock=lock, queue=node.fast_queue,
                           tg=TG_DC_UNBOUND)

        if err:
            return FailureTaskResponse(self.request, err, dc_bound=False)
        else:
            return TaskResponse(self.request, tid, msg=msg, obj=node, api_view=_apiview_, data=self.data,
                                dc_bound=False, detail_dict=ser.detail_dict(force_full=True))


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
