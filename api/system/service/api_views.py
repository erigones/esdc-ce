from api.api_views import APIView
from api.exceptions import ObjectNotFound
from api.task.response import SuccessTaskResponse
from api.system.service.control import ServiceControl


class ServiceStatusView(APIView):
    dc_bound = False

    # noinspection PyUnusedLocal
    def __init__(self, request, service, data=None):
        super(ServiceStatusView, self).__init__(request)
        self.service = service
        self.ctrl = ServiceControl()

        if service and service not in self.ctrl.services:
            raise ObjectNotFound(object_name='Service')

    def get(self):
        """Return service status or a list of all service statuses"""
        if self.service:
            res = self.ctrl.status(self.service)
        else:
            res = self.ctrl.status_all()

        return SuccessTaskResponse(self.request, res, dc_bound=False)
