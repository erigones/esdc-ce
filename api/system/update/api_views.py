import os
from logging import getLogger
from django.conf import settings

from api.api_views import APIView
from api.exceptions import TaskIsAlreadyRunning, PreconditionRequired
from api.system.messages import LOG_SYSTEM_UPDATE
from api.system.update.serializers import UpdateSerializer
from api.system.update.events import SystemUpdateStarted, SystemUpdateFinished
from api.system.update.utils import process_update_reply
from api.system.service.control import SystemReloadThread
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from que import TG_DC_UNBOUND, TT_DUMMY
from que.handlers import update_command
from que.utils import task_id_from_request
from que.lock import TaskLock
from vms.models import DefaultDc

logger = getLogger(__name__)


class UpdateResult(dict):
    def __init__(self, update, success=False, rc=None, msg=None, **kwargs):
        update = os.path.basename(update)
        super(UpdateResult, self).__init__(update=update, success=success, rc=rc, msg=msg, **kwargs)

    @property
    def log_detail(self):
        return SuccessTaskResponse.dict_to_detail(self)


class UpdateView(APIView):
    """
    Update Danube Cloud application.
    """
    dc_bound = False
    _updates = ()
    _installed = 0
    _lock_key = 'system_update'

    def __init__(self, request, data):
        super(UpdateView, self).__init__(request, force_default_dc=True)
        self.data = data
        self.user = request.user
        self.task_id = task_id_from_request(self.request, dummy=True, tt=TT_DUMMY, tg=TG_DC_UNBOUND)

    def _update(self, version, key=None, cert=None):
        logger.debug('Running system update to version: "%s"', version)
        reply = update_command(version, key=key, cert=cert, sudo=not settings.DEBUG)
        response_class, result = process_update_reply(reply, 'system', version)
        response = response_class(self.request, result, task_id=self.task_id, msg=LOG_SYSTEM_UPDATE,
                                  detail_dict=result, dc_bound=False)

        if response.status_code == 200:
            # Restart all gunicorns and erigonesd!
            SystemReloadThread(task_id=self.task_id, request=self.request, reason='system_update').start()

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

        version = ser.object['version']
        from core.version import __version__ as mgmt_version

        # noinspection PyUnboundLocalVariable
        if version == ('v' + mgmt_version):
            raise PreconditionRequired('System is already up-to-date')

        lock = self.get_task_lock()

        if not lock.acquire(self.task_id, timeout=7200, save_reverse=False):
            raise TaskIsAlreadyRunning

        try:
            # Emit event into socket.io
            SystemUpdateStarted(self.task_id, request=self.request).send()

            return self._update(version, key=ser.object.get('key'), cert=ser.object.get('cert'))
        finally:
            lock.delete(fail_silently=True, delete_reverse=False)
            # Emit event into socket.io
            SystemUpdateFinished(self.task_id, request=self.request).send()
