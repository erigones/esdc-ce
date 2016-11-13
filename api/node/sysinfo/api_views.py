from api.api_views import APIView
from api.task.response import TaskResponse, FailureTaskResponse
from api.node.utils import get_node
from api.exceptions import NodeIsNotOperational
from api.node.messages import LOG_NODE_UPDATE
from que.tasks import execute_sysinfo


class NodeSysinfoView(APIView):
    """
    api.node.sysinfo.views.node_sysinfo
    """
    dc_bound = False

    def __init__(self, request, hostname, data):
        super(NodeSysinfoView, self).__init__(request)
        self.node = get_node(request, hostname)
        self.data = data

    def put(self):
        """
        Performs call to execute_sysinfo
        """
        if not self.node.is_online():
            raise NodeIsNotOperational()

        apiview = {
            'view': 'node_sysinfo',
            'method': self.request.method,
            'hostname': self.node.hostname,
        }
        meta = {
            'apiview': apiview,
            'msg': LOG_NODE_UPDATE,
            'node_uuid': self.node.uuid,

        }
        task_id, err = execute_sysinfo(self.request, self.node.owner.id, queue=self.node.fast_queue, meta=meta,
                                       node_uuid=self.node.uuid, check_user_tasks=True)

        if err:
            return FailureTaskResponse(self.request, err)
        else:
            return TaskResponse(self.request, task_id, api_view=apiview, obj=self.node, msg=LOG_NODE_UPDATE,
                                data=self.data)
